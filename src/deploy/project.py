import datetime
import functools
import typing

import cattr
import yaml

from . import ecs, iam, models
from .ecr import EcrPrivate, get_ecr_image_description, parse_ecr_image_uri
from .exceptions import ConfigError, WecoDeployError, NothingToReleaseError
from .release_store import DynamoReleaseStore

DEFAULT_REGION_NAME = "eu-west-1"


def _load(filepath):
    with open(filepath) as infile:
        return yaml.safe_load(infile)


class Projects:
    def __init__(self, project_filepath):
        self.projects = _load(project_filepath)

    def list(self):
        return list(self.projects.keys())

    def load(self, project_id, **kwargs):
        try:
            config = self.projects[project_id]
        except KeyError:
            raise ConfigError(f"No matching project {project_id} in {self.projects}")

        try:
            region_name = config["region_name"]
        except KeyError:
            region_name = DEFAULT_REGION_NAME

        release_store = DynamoReleaseStore(
            project_id=project_id,
            region_name=region_name,
            role_arn=config["role_arn"]
        )

        return Project(
            project_id=project_id,
            config=config,
            release_store=release_store
        )


def compare_image_specs(
    sess,
    service_name: str,
    task_id: str,
    expected_images: typing.Dict[str, models.DockerImageSpec],
    actual_images: typing.Dict[str, models.DockerImageSpec],
):
    """
    Print a summary of the differences in the expected/actual images.

    This is meant for human-readability.
    """
    assert expected_images != actual_images

    print("")
    print(f"Task {task_id} in {service_name} has the wrong containers:")

    for name, actual_spec in actual_images.items():
        try:
            expected_spec = expected_images[name]
            if expected_spec.uri != actual_spec.uri:
                print(f"- {name}: wrong URI")
                print(f"    expected: {expected_spec.uri}")
                print(f"    actual:   {actual_spec.uri}")

            if expected_spec.digest != actual_spec.digest:
                expected_image = parse_ecr_image_uri(expected_spec.uri)
                actual_image = parse_ecr_image_uri(actual_spec.uri)

                expected_description = get_ecr_image_description(
                    sess,
                    registry_id=expected_image["registry_id"],
                    repository_name=expected_image["repository_name"],
                    image_digest=expected_spec.digest
                )

                actual_description = get_ecr_image_description(
                    sess,
                    registry_id=actual_image["registry_id"],
                    repository_name=actual_image["repository_name"],
                    image_digest=actual_spec.digest
                )

                print(f"- {name}: wrong image digest")
                print(f"    expected: {expected_description}")
                print(f"              {expected_spec.digest}")
                print(f"    actual:   {actual_description}")
                print(f"              {actual_spec.digest}")
        except KeyError:
            print(f"- {name}: unexpected container running")

    for name in expected_images:
        if name not in actual_images:
            print(f"- {name}: expected container, but wasn't found")


class Project:
    def __init__(self, project_id, config, release_store):
        self.id = project_id
        self._underlying = cattr.structure(config, models.Project)

        self.config = config
        self.config["id"] = project_id

        self.release_store = release_store
        self.release_store.initialise()

        self.session = iam.get_session(
            "weco-deploy-project",
            role_arn=self.role_arn,
            region_name=self.region_name
        )

        # This tracks tasks whose state we've already reported as being
        # not up-to-date; we don't need to log them again.
        self._already_checked_tasks = set()

    @property
    @functools.lru_cache()
    def ecr(self):
        return EcrPrivate(region_name=self.region_name, role_arn=self.role_arn)

    @property
    def role_arn(self):
        return self._underlying.role_arn

    @property
    def region_name(self):
        return self._underlying.region_name

    @property
    def image_repositories(self):
        return self._underlying.image_repositories

    @property
    def environment_names(self):
        return self._underlying.environments

    def _create_deployment(self, environment_id, details, description):
        return {
            "environment": environment_id,
            "date_created": datetime.datetime.utcnow().isoformat(),
            "requested_by": iam.get_underlying_role_arn(),
            "description": description,
            "details": details
        }

    def has_up_to_date_tasks(self, release, environment_id, verbose=False):
        """
        Checks whether all the running tasks in the project are using
        the correct versions of the images.
        """
        # Get a list of all the services that are affected by this change.
        #
        # NOTE: weco-deploy only ever deploys within a single ECS cluster,
        # so we could simplify this if we specify the cluster name upfront --
        # but for now, listing all the services is the way to go.
        service_descriptions = ecs.describe_services(self.session)

        ecs_services = ecs.find_ecs_services_for_release(
            project=self._underlying,
            service_descriptions=service_descriptions,
            release=release,
            environment_id=environment_id,
        )

        affected_services = []

        for _, services in ecs_services.items():
            for serv in services.values():
                affected_services.append(
                    {
                        "cluster": serv["clusterArn"],
                        "service_name": serv["serviceName"],
                        "desired_count": serv["desiredCount"],
                    }
                )

        # Now get the service spec for each of these services.
        #
        # This tells us what containers we expect to have deployed as
        # part of this service.
        for serv in affected_services:
            serv["spec"] = ecs.get_ecs_service_spec(
                self.session, cluster=serv["cluster"], service_name=serv["service_name"]
            )

        # Now loop through all these services, inspect the running tasks,
        # and check if they match the service spec.
        is_up_to_date = True

        def printv(str):
            if verbose:
                print(str)

        for serv in affected_services:
            running_tasks = ecs.list_tasks_in_service(
                self.session, cluster=serv["cluster"], service_name=serv["service_name"]
            )

            for task in running_tasks:
                actual_images = {
                    container["name"]: models.DockerImageSpec(
                        uri=container["image"],
                        digest=container.get("imageDigest", "<none>"),
                    )
                    for container in task["containers"]
                }

                expected_images = serv["spec"].images

                task_id = task["taskArn"].split("/")[-1]

                if actual_images != expected_images:
                    if verbose and task_id not in self._already_checked_tasks:
                        compare_image_specs(
                            self.session,
                            service_name=serv["service_name"],
                            task_id=task_id,
                            actual_images=actual_images,
                            expected_images=expected_images,
                        )
                    elif verbose:
                        print(f"Still waiting for task {task_id} in {serv['service_name']} to stop")

                    self._already_checked_tasks.add(task_id)

                    is_up_to_date = False

                if task["lastStatus"] != "RUNNING":
                    printv("")
                    print(f"Task {task_id} in {serv['service_name']} has the wrong status:")
                    printv("  expected: RUNNING")
                    printv(f"  actual:   {task['lastStatus']}")
                    is_up_to_date = False

            if len(running_tasks) < serv["desired_count"]:
                printv("")
                printv(f"Not running enough tasks in {serv['service_name']}:")
                printv(f"  expected: {serv['desired_count']}")
                printv(f"  actual:   {len(running_tasks)}")
                is_up_to_date = False

        return is_up_to_date

    def get_images(self, from_label):
        """
        Returns a dict (image id) -> (Git ref tag).

        Note: a single Docker image may have multiple ref tags, so the ref tag
        is chosen arbitrarily.
        """
        ref_tags_resp = self.ecr.get_ref_tags_for_repositories(
            image_repositories=self.image_repositories.keys(),
            tag=from_label
        )

        # An image might have multiple ref tags if it was pushed at multiple
        # Git commits with the same code.  In this case, choose a ref arbitrarily.
        result = {}

        for image_id, ref_tags in ref_tags_resp.items():
            try:
                result[image_id] = ref_tags.pop()
            except KeyError:  # No images
                result[image_id] = None

        return result

    def prepare(self, from_label, description):
        release_images = self.get_images(from_label)

        services_to_release = [service_id for service_id, release_ref in release_images.items() if
                               release_ref is not None]

        if not services_to_release:
            raise NothingToReleaseError("No images to release!")

        return self.release_store.prepare_release(
            project_id=self.id,
            project=self._underlying,
            description=description,
            release_images=release_images
        )

    def update(self, release_id, service_ids, from_label):
        release = self.release_store.get_release(release_id)
        images = self.get_images(from_label)

        # Ensure all specified services are available as images
        for service_id in service_ids:
            if service_id not in images.keys():
                raise WecoDeployError(f"No images found for {service_id}")

        # Filter to only specified images
        filtered_images = {k: v for k, v in images.items() if k in service_ids}

        # Merge images from specified release with those from service
        release_images = {**release['images'], **filtered_images}

        description = f"Release based on {release_id}, updating {service_ids} to {from_label}"

        return self.release_store.prepare_release(
            project_id=self.id,
            project=self._underlying,
            description=description,
            release_images=release_images
        )

    def _tag_ecr_image(self, environment_id, image_id, image_name):
        old_tag = image_name.split(":")[-1]
        new_tag = f"env.{environment_id}"

        return self.ecr.tag_image(
            image_id=image_id,
            tag=old_tag,
            new_tag=new_tag
        )

    def deploy(self, release_id, environment_id, description):
        release = self.release_store.get_release(release_id)

        if release is None:
            raise WecoDeployError(f"No releases found {release_id}, cannot continue!")

        # Force check for valid environment
        if environment_id not in self.environment_names:
            raise WecoDeployError(
                f"Unknown environment. "
                f"Got {environment_id!r}, expected {self.environment_names.keys()!r}"
            )

        deployment_details = {}

        ecs_services_deployed = {}

        # Memoize service deployments to prevent multiple deployments
        def _ecs_deploy(service):
            cluster_arn = service["clusterArn"]
            service_arn = service["serviceArn"]

            if service_arn not in ecs_services_deployed:
                ecs_services_deployed[service_arn] = ecs.deploy_service(
                    self.session,
                    cluster_arn=cluster_arn,
                    service_arn=service_arn,
                )

            return ecs_services_deployed[service_arn]

        service_descriptions = ecs.describe_services(self.session)

        matched_services = ecs.find_ecs_services_for_release(
            project=self._underlying,
            service_descriptions=service_descriptions,
            release=release,
            environment_id=environment_id
        )

        for image_id, image_name in sorted(release['images'].items()):
            if image_name is None:
                continue

            tag_result = self._tag_ecr_image(
                environment_id=environment_id,
                image_id=image_id,
                image_name=image_name
            )

            if tag_result['status'] == 'noop':
                ecs_deployments = []
            else:
                ecs_deployments = [
                    _ecs_deploy(service)
                    for service in matched_services.get(image_id, {}).values()
                ]

            deployment_details[image_id] = {
                'tag_result': tag_result,
                'ecs_deployments': ecs_deployments
            }

        deployment = self._create_deployment(environment_id, deployment_details, description)

        self.release_store.add_deployment(
            release_id=release['release_id'],
            deployment=deployment
        )

        return deployment
