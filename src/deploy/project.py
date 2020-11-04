import collections
import datetime
import functools
import uuid
import warnings

import yaml

from . import ecr
from .ecr import Ecr
from .ecs import Ecs
from .exceptions import ConfigError
from .releases_store import DynamoDbReleaseStore
from .iam import Iam
from .tags import parse_aws_tags

DEFAULT_ECR_NAMESPACE = "uk.ac.wellcome"
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

        return Project(project_id=project_id, config=config, **kwargs)


def prepare_config(config, namespace=None, role_arn=None, region_name=None):
    """
    Prepare the config.  Fill in overrides or defaults as necessary.
    """
    # We always want a namespace to be set.  Read it from the initial config
    # if possible, or use the override or default if not.
    if namespace and ("namespace" in config) and (config["namespace"] != namespace):
        warnings.warn(
            f"Preferring override namespace {namespace} "
            f"to namespace in config {config['namespace']}"
        )
        config["namespace"] = namespace
    elif "namespace" not in config:
        config["namespace"] = namespace or DEFAULT_ECR_NAMESPACE

    assert "namespace" in config

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
    def __init__(self, project_id, config, account_id=None, **kwargs):
        prepare_config(config, **kwargs)
        self.config = config

        self.config['id'] = project_id

        iam = Iam(
            self.config['role_arn'],
            self.config['region_name']
        )

        self.user_details = {
            'caller_identity': iam.caller_identity(),
            'underlying_caller_identity': iam.caller_identity(underlying=True)
        }

        if account_id:
            self.config['account_id'] = account_id
        else:
            if 'account_id' not in self.config:
                self.config['account_id'] = self.user_details['caller_identity']['account_id']

        # Initialise project level vars
        self.image_repositories = self.config.get('image_repositories', [])

        # Create required services
        self.releases_store = DynamoDbReleaseStore(
            project_id=self.id,
            region_name=self.region_name,
            role_arn=self.role_arn
        )

        # Ensure release store is available
        self.releases_store.initialise()

    @property
    def id(self):
        return self.config["id"]

    @property
    def role_arn(self):
        return self.config["role_arn"]

    @property
    def region_name(self):
        return self.config["region_name"]

    @property
    def account_id(self):
        return self.config["account_id"]

    @property
    def namespace(self):
        return self.config["namespace"]

    def _ecr(self, account_id=None, region_name=None, role_arn=None):
        return Ecr(
            account_id=account_id or self.account_id,
            region_name=region_name or self.region_name,
            role_arn=role_arn or self.role_arn
        )

    @functools.lru_cache()
    def _ecs(self, region_name=None, role_arn=None):
        return Ecs(
            region_name=region_name or self.region_name,
            role_arn=role_arn or self.role_arn
        )

    def _create_deployment(self, environment_id, details, description):
        return {
            "environment": environment_id,
            "date_created": datetime.datetime.utcnow().isoformat(),
            "requested_by": self.user_details['underlying_caller_identity']['arn'],
            "description": description,
            "details": details
        }

    def _create_release(self, description, images):
        release_id = str(uuid.uuid4())

        return {
            "release_id": release_id,
            "project_id": self.id,
            "project_name": self.config.get('name', 'unnamed'),
            "date_created": datetime.datetime.utcnow().isoformat(),
            "requested_by": self.user_details['underlying_caller_identity']['arn'],
            "description": description,
            "images": images,
            "deployments": []
        }

    def _match_image_id(self, image_id):
        matched_images = [image for image in self.image_repositories if image['id'] == image_id]

        if len(matched_images) > 1:
            raise RuntimeError(f"Multiple matching images found for {image_id}: ({matched_images}!")

        if matched_images:
            return matched_images[0]
        else:
            return None

    def get_environment(self, environment_id):
        environments = {
            e['id']: e for e in self.config.get('environments', []) if 'id' in e
        }

        if environment_id not in environments:
            raise ValueError(f"Unknown environment. Expected '{environment_id}' in {environments}")

        return environments[environment_id]

    def get_deployments(self, release_id, limit):
        if release_id is not None:
            release = self.releases_store.get_release(release_id)

            for d in release["deployments"]:
                d["release_id"] = release_id

            deployments = release_id["deployments"]
        else:
            deployments = self.releases_store.get_recent_deployments(limit=limit)

        deployments = sorted(deployments, key=lambda d: d["date_created"], reverse=True)
        return deployments[:limit]

    def get_release(self, release_id):
        if release_id == "latest":
            return self.releases_store.get_latest_release()
        else:
            return self.releases_store.get_release(release_id)

    def _get_services_by_image_id(self, release):
        """
        Generates a set of tuples (image_id, List[services])
        """
        for image_id, _ in release["images"].items():
            # TODO: self.image_repositories should be a dict, not a list
            matched_image = self._match_image_id(image_id)

            # TODO: Should this ever happen?
            if matched_image is None:
                continue

            try:
                services = matched_image["services"]
            except KeyError:
                continue

            yield (image_id, services)

    def get_ecs_service_arns(self, release, environment_id):
        """
        Returns a dict (image ID) -> List[service ARNs].
        """
        result = collections.defaultdict(list)

        for image_id, services in self._get_services_by_image_id(release):
            for serv in services:
                ecs = self._ecs(
                    region_name=serv.get('region_name'),
                    role_arn=serv.get('role_arn')
                )

                matching_service = ecs.find_matching_service(
                    service_id=serv["id"],
                    environment_id=environment_id
                )

                try:
                    result[image_id].append(matching_service["serviceArn"])
                except TypeError:
                    assert matching_service is None, matching_service

        return dict(result)

    def get_ecs_services(self, release, environment_id):
        def _get_service(service):
            ecs = self._ecs(
                region_name=service.get('region_name'),
                role_arn=service.get('role_arn')
            )

            ecs_service = ecs.find_matching_service(
                service_id=service['id'],
                environment_id=environment_id
            )

            return {
                'config': service,
                'response': ecs_service
            }

        matched_services = {}
        for image_id, _ in release['images'].items():
            # Attempt to match deployment image id to config and override service_ids
            matched_image = self._match_image_id(image_id)

            available_services = []

            if matched_image:
                services = matched_image.get('services', [])

                available_services = [_get_service(service) for service in services]
                available_services = [service for service in available_services if service["response"]]

            if available_services:
                matched_services[image_id] = available_services

        return matched_services

    def is_release_deployed(self, release, environment_id):
        """
        Checks the `deployment:label` tag on a service matches the tags
        on the tasks within those services. We check that the desiredCount
        of tasks matches the running count of tasks.
        """
        ecs_services = self.get_ecs_services(release, environment_id)

        is_deployed = True

        for _, services in sorted(ecs_services.items()):
            for service in services:
                service_tags = parse_aws_tags(service["response"]["tags"])
                service_deployment_label = service_tags["deployment:label"]
                desired_task_count = service["response"]["desiredCount"]
                ecs = self._ecs(
                    region_name=service.get('region_name'),
                    role_arn=service.get('role_arn')
                )
                tasks = ecs.list_service_tasks(service)

                for task in tasks:
                    task_tags = parse_aws_tags(task["tags"])

                    task_name = task_tags.get("deployment:service")
                    deployment_label = task_tags.get("deployment:label")

                    if deployment_label != service_deployment_label:
                        task_arn = task["taskArn"]
                        print("")
                        print(f"Task in {task_name} has the wrong deployment label:")
                        print(f"Wanted:   {service_deployment_label}")
                        print(f"Actual:   {deployment_label}")
                        print(f"Task ARN: {task_arn}")
                        is_deployed = False

                    if task["lastStatus"] != "RUNNING":
                        print("")
                        print(f"Task in {task_name} has the wrong status:")
                        print("Wanted:   RUNNING")
                        print(f"Actual:   {task['lastStatus']}")
                        print(f"Task ARN: {task_arn}")
                        is_deployed = False

                if len(tasks) < desired_task_count:
                    print("")
                    print(f"Not running the correct number of tasks in {service}:")
                    print(f"Wanted: {desired_task_count}")
                    print(f"Actual: {len(tasks)}")
                    is_deployed = False

        return is_deployed

    def publish(self, image_id, label):
        # Attempt to match image to config
        matched_image = self._match_image_id(image_id)

        # Assume default account id & namespace
        account_id = self.account_id
        namespace = self.namespace

        # If we find a match, set overrides
        if matched_image:
            # Check if namespace/account_id is overridden for this image
            namespace = matched_image.get('namespace', self.namespace)
            account_id = matched_image.get('account_id', self.account_id)

        # Create an ECR client for the correct account
        ecr = self._ecr(account_id)

        ecr.login()

        remote_uri, remote_tag, local_tag = ecr.publish_image(
            namespace=namespace,
            image_id=image_id,
        )

        tag_result = ecr.tag_image(
            namespace=namespace,
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
        image_repositories = {}

        for repo in self.image_repositories:
            namespace = repo.get("namespace", self.namespace)

            image_repositories[repo["id"]] = {
                "account_id": repo.get("account_id", self.account_id),
                "region_name": repo.get("region_name", self.region_name),
                "role_arn": repo.get("role_arn", self.role_arn),
                "repository_name": f"{namespace}/{repo['id']}"
            }

        return ecr.get_ref_tags_for_repositories(
            image_repositories=image_repositories,
            tag=from_label
        )

    def _prepare_release(self, description, release_images):
        previous_release = self.releases_store.get_latest_release()

        new_release = self._create_release(
            description=description,
            images=release_images
        )

        self.releases_store.put_release(new_release)

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
        return self._ecs(
            region_name=service['config'].get('region_name'),
            role_arn=service['config'].get('role_arn'),
        ).redeploy_service(
            cluster_arn=service['response']['clusterArn'],
            service_arn=service['response']['serviceArn'],
            deployment_label=deployment_label
        )

    def _tag_ecr_image(self, environment_id, image_id, image_name):
        old_tag = image_name.split(":")[-1]
        new_tag = f"env.{environment_id}"

        matched_image = self._match_image_id(image_id)
        if matched_image:
            ecr = self._ecr(
                account_id=matched_image.get('account_id'),
                region_name=matched_image.get('region_name'),
                role_arn=matched_image.get('role_arn'),
            )
        else:
            ecr = self._ecr()

        return ecr.tag_image(
            namespace=self.namespace,
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
        _ = self.get_environment(environment_id)

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

        self.releases_store.add_deployment(release['release_id'], deployment)

        return deployment
