import datetime
import functools
import uuid
import warnings

import cattr
import yaml

from . import ecr, iam, models
from .ecr import Ecr
from .ecs import Ecs, find_matching_service
from .exceptions import ConfigError
from .release_store import DynamoReleaseStore, ReleaseNotFoundError
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

        prepare_config(config, **kwargs)

        release_store = DynamoReleaseStore(
            project_id=project_id,
            region_name=config["region_name"],
            role_arn=config["role_arn"]
        )

        return Project(
            project_id=project_id,
            config=config,
            release_store=release_store
        )


def prepare_config(
        config,
        *,
        role_arn=None,
        region_name=None
):
    """
    Prepare the config.  Fill in overrides or defaults as necessary.
    """
    # We always want a role_arn to be set.  Read it from the initial config,
    # or raise an error if not -- there's no way to pick a sensible default.
    if role_arn:
        if ("role_arn" in config) and (config["role_arn"] != role_arn):
            warnings.warn(
                f"Preferring override role_arn {role_arn} "
                f"to role_arn in config {config['role_arn']}"
            )
            config["role_arn"] = role_arn
        elif "role_arn" not in config:
            config["role_arn"] = role_arn

    if "role_arn" not in config:
        raise ConfigError("role_arn is not set!")

    assert "role_arn" in config

    # We always want a region_name to be set.  Read it from the initial config
    # if possible, or use the override or default if not.
    if region_name and ("region_name" in config) and (config["region_name"] != region_name):
        warnings.warn(
            f"Preferring override region_name {region_name} "
            f"to region_name in config {config['region_name']}"
        )
        config["region_name"] = region_name
    elif "region_name" not in config:
        config["region_name"] = region_name or DEFAULT_REGION_NAME

    assert "region_name" in config


class Project:
    def __init__(self, project_id, config, release_store):
        self.id = project_id
        self._underlying = cattr.structure(config, models.Project)

        self.config = config
        self.config["id"] = project_id

        self.release_store = release_store
        self.release_store.initialise()

    @property
    @functools.lru_cache()
    def ecs(self):
        return self.ecs_no_cache

    @property
    def ecs_no_cache(self):
        return Ecs(
            region_name=self.region_name,
            role_arn=self.role_arn
        )

    @property
    @functools.lru_cache()
    def ecr(self):
        return Ecr(region_name=self.region_name, role_arn=self.role_arn)

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

    def _create_release(self, description, images):
        release_id = str(uuid.uuid4())

        return {
            "release_id": release_id,
            "project_id": self.id,
            "project_name": self._underlying.name,
            "date_created": datetime.datetime.utcnow().isoformat(),
            "requested_by": iam.get_underlying_role_arn(),
            "description": description,
            "images": images,
            "deployments": []
        }

    def get_deployments(self, release_id, limit, environment_id):
        if release_id is not None:
            release = self.release_store.get_release(release_id)

            # TODO: I think the release ID is already stored on the deployments.
            # Can we remove this loop?
            for d in release["deployments"]:
                assert d["release_id"] == release_id

            deployments = release["deployments"]
        else:
            deployments = self.release_store.get_recent_deployments(
                environment=environment_id,
                limit=limit
            )

        deployments = sorted(deployments, key=lambda d: d["date_created"], reverse=True)
        return deployments[:limit]

    def get_release(self, release_id):
        if release_id == "latest":
            return self.release_store.get_most_recent_release()
        else:
            return self.release_store.get_release(release_id)

    def get_ecs_services(self, release, environment_id, cached=True):
        def _get_service(service_id):
            # Sometimes we want not to use the service cache - eg when checking
            # whether deployments succeeded, we want a fresh copy of the services
            # information.
            if not cached:
                ecs = self.ecs_no_cache
            else:
                ecs = self.ecs

            ecs_service = find_matching_service(
                service_descriptions=ecs._described_services,
                service_id=service_id,
                environment_id=environment_id
            )

            return {
                'config': {"id": service_id},
                'response': ecs_service
            }

        matched_services = {}
        for image_id, _ in release['images'].items():
            # Attempt to match deployment image id to config and override service_ids
            try:
                matched_image = self.image_repositories[image_id]
            except KeyError:
                continue

            services = matched_image.get('services', [])

            available_services = [_get_service(service_id) for service_id in services]
            available_services = [service for service in available_services if service["response"]]

            if available_services:
                matched_services[image_id] = available_services

        return matched_services

    def is_release_deployed(self, release, environment_id, verbose=False):
        """
        Checks the `deployment:label` tag on a service matches the tags
        on the tasks within those services. We check that the desiredCount
        of tasks matches the running count of tasks.
        """
        ecs_services = self.get_ecs_services(release, environment_id, cached=False)

        def printv(str):
            if verbose:
                print(str)

        is_deployed = True

        for _, services in sorted(ecs_services.items()):
            for service in services:
                service_tags = parse_aws_tags(service["response"]["tags"])
                service_arn = service["response"]["serviceArn"]
                service_deployment_label = service_tags["deployment:label"]
                desired_task_count = service["response"]["desiredCount"]
                tasks = self.ecs.list_service_tasks(service)

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

    def publish(self, image_id, label):
        # Create an ECR client for the correct account
        self.ecr.login()

        remote_uri, remote_tag, local_tag = self.ecr.publish_image(
            image_id=image_id,
        )

        tag_result = self.ecr.tag_image(
            image_id=image_id,
            tag=remote_tag,
            new_tag=label
        )

        return {
            'ecr_push': {
                'local_tag': local_tag,
                'remote_tag': remote_tag,
                'remote_uri': remote_uri,
            },
            'ecr_tag': tag_result
        }

    def get_images(self, from_label):
        """
        Returns a dict (image id) -> (Git ref tag).

        Note: a single Docker image may have multiple ref tags, so the ref tag
        is chosen arbitrarily.
        """
        ref_tags_resp = ecr.get_ref_tags_for_repositories(
            self.ecr._underlying.client,
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

    def _prepare_release(self, description, release_images):
        try:
            previous_release = self.release_store.get_most_recent_release()
        except ReleaseNotFoundError:
            previous_release = None

        new_release = self._create_release(
            description=description,
            images=release_images
        )

        self.release_store.put_release(new_release)

        return {"previous_release": previous_release, "new_release": new_release}

    def prepare(self, from_label, description):
        release_images = self.get_images(from_label)

        if not release_images:
            raise RuntimeError(f"No images found for {self.id}/{from_label}")

        return self._prepare_release(
            description=description,
            release_images=release_images
        )

    def update(self, release_id, service_ids, from_label):
        release = self.get_release(release_id)
        images = self.get_images(from_label)

        # Ensure all specified services are available as images
        for service_id in service_ids:
            if service_id not in images.keys():
                raise RuntimeError(f"No images found for {service_id}")

        # Filter to only specified images
        filtered_images = {k: v for k, v in images.items() if k in service_ids}

        # Merge images from specified release with those from service
        release_images = {**release['images'], **filtered_images}

        description = f"Release based on {release_id}, updating {service_ids} to {from_label}"

        return self._prepare_release(
            description=description,
            release_images=release_images
        )

    def _deploy_ecs_service(self, service, deployment_label):
        return self.ecs.redeploy_service(
            cluster_arn=service['response']['clusterArn'],
            service_arn=service['response']['serviceArn'],
            deployment_label=deployment_label
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
        release = self.get_release(release_id)

        if release is None:
            raise ValueError(f"No releases found {release_id}, cannot continue!")

        matched_services = self.get_ecs_services(
            release=release,
            environment_id=environment_id
        )

        # Force check for valid environment
        if environment_id not in self.environment_names:
            raise ValueError(
                f"Unknown environment. "
                f"Got {environment_id!r}, expected {self.environment_names.keys()!r}"
            )

        deployment_details = {}

        ecs_services_deployed = {}

        # Memoize service deployments to prevent multiple deployments
        def _ecs_deploy(service, deployment_label):
            if service['response']['serviceArn'] not in ecs_services_deployed:
                ecs_services_deployed[service['response']['serviceArn']] = self._deploy_ecs_service(
                    service=service,
                    deployment_label=deployment_label
                )

            return ecs_services_deployed[service['response']['serviceArn']]

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
                    for service in matched_services.get(image_id, [])
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
