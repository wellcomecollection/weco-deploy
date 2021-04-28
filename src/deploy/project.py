import datetime
import functools

import cattr
import yaml

from . import ecs, iam, models
from .ecr import EcrPrivate
from .exceptions import ConfigError, WecoDeployError
from .release_store import DynamoReleaseStore
from .tags import parse_aws_tags

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

    def is_release_deployed(self, release, environment_id, verbose=False):
        """
        Checks the `deployment:label` tag on a service matches the tags
        on the tasks within those services. We check that the desiredCount
        of tasks matches the running count of tasks.
        """
        service_descriptions = ecs.describe_services(self.session)

        ecs_services = ecs.find_ecs_services_for_release(
            project=self._underlying,
            service_descriptions=service_descriptions,
            release=release,
            environment_id=environment_id
        )

        def printv(str):
            if verbose:
                print(str)

        is_deployed = True

        for _, services in sorted(ecs_services.items()):
            for service_resp in services.values():
                service_tags = parse_aws_tags(service_resp["tags"])
                service_arn = service_resp["serviceArn"]
                service_deployment_label = service_tags["deployment:label"]
                desired_task_count = service_resp["desiredCount"]

                tasks = ecs.list_tasks_in_service(
                    self.session,
                    cluster_arn=service_resp["clusterArn"],
                    service_name=service_resp["serviceName"],
                )

                for task in tasks:
                    task_tags = parse_aws_tags(task["tags"])
                    task_arn = task["taskArn"]

                    task_name = task_tags.get("deployment:service")
                    deployment_label = task_tags.get("deployment:label")

                    if deployment_label != service_deployment_label:
                        printv("")
                        printv(f"Task in {task_name} has the wrong deployment label:")
                        printv(f"Wanted:   {service_deployment_label}")
                        printv(f"Actual:   {deployment_label}")
                        printv(f"Task ARN: {task_arn}")
                        is_deployed = False

                    if task["lastStatus"] != "RUNNING":
                        printv("")
                        printv(f"Task in {task_name} has the wrong status:")
                        printv("Wanted:   RUNNING")
                        printv(f"Actual:   {task['lastStatus']}")
                        printv(f"Task ARN: {task_arn}")
                        is_deployed = False

                if len(tasks) < desired_task_count:
                    printv("")
                    printv(f"Not running the correct number of tasks in {service_arn}:")
                    printv(f"Wanted: {desired_task_count}")
                    printv(f"Actual: {len(tasks)}")
                    is_deployed = False

        return is_deployed

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

        if not release_images:
            raise WecoDeployError(f"No images found for {self.id}/{from_label}")

        for service_id, release_ref in release_images.items():
            if release_ref is None:
                raise WecoDeployError(f"No image found for {self.id}/{from_label}/{service_id}")

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
        def _ecs_deploy(service, deployment_label):
            cluster_arn = service["clusterArn"]
            service_arn = service["serviceArn"]

            if service_arn not in ecs_services_deployed:
                ecs_services_deployed[service_arn] = ecs.deploy_service(
                    self.session,
                    cluster_arn=cluster_arn,
                    service_arn=service_arn,
                    deployment_label=deployment_label
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
            tag_result = self._tag_ecr_image(
                environment_id=environment_id,
                image_id=image_id,
                image_name=image_name
            )

            if tag_result['status'] == 'noop':
                ecs_deployments = []
            else:
                ecs_deployments = [
                    _ecs_deploy(
                        service=service,
                        deployment_label=release['release_id']
                    )
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
