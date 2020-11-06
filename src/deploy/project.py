import collections
import datetime
import functools
import uuid
import warnings

import yaml

from . import ecr, iam
from .ecr import Ecr
from .ecs import Ecs
from .exceptions import ConfigError
from .release_store import DynamoReleaseStore
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
    namespace=None,
    role_arn=None,
    region_name=None,
    account_id=None
):
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

    # The image repositories are stored as a list of dicts:
    #
    #     [
    #       {"id": "worker1", "services": […]},
    #       {"id": "worker2", "services": […]},
    #       ...
    #     ]
    #
    # We don't want to change the structure, but we do want to check that IDs
    # are unique.
    repo_id_tally = collections.Counter()
    for repo in config.get("image_repositories", []):
        repo_id_tally[repo["id"]] += 1

    duplicates = {repo_id for repo_id, count in repo_id_tally.items() if count > 1}
    if duplicates:
        raise ConfigError(
            f"Duplicate repo{'s' if len(duplicates) > 1 else ''} "
            f"in image_repositories: {', '.join(sorted(duplicates))}"
        )

    # The environments are stored as a list of dicts:
    #
    #     [
    #       {"id": "stage", "name": […]},
    #       {"id": "prod", "name": […]},
    #       ...
    #     ]
    #
    # We don't want to change the structure, but we do want to check that IDs
    # are unique.
    env_id_tally = collections.Counter()
    for env in config.get("environments", []):
        env_id_tally[env["id"]] += 1

    duplicates = {env_id for env_id, count in env_id_tally.items() if count > 1}
    if duplicates:
        raise ConfigError(
            f"Duplicate environment{'s' if len(duplicates) > 1 else ''} "
            f"in config: {', '.join(sorted(duplicates))}"
        )

    # We always want an account_id to be set.  Read it from the initial config
    # if possible, or use the override or guess it from the role ARN if not.
    if account_id and ("account_id" in config) and (config["account_id"] != account_id):
        warnings.warn(
            f"Preferring override account_id {account_id} "
            f"to account_id in config {config['account_id']}"
        )
        config["account_id"] = account_id

    iam_role_account_id = iam.get_account_id(config["role_arn"])
    if ("account_id" in config) and (config["account_id"] != iam_role_account_id):
        warnings.warn(
            f"Account ID {config['account_id']} does not match the role {config['role_arn']}"
        )

    if "account_id" not in config:
        config["account_id"] = iam_role_account_id

    assert "account_id" in config


class Project:
    def __init__(self, project_id, config, release_store):
        self.config = config

        self.config["id"] = project_id

        self.release_store = release_store
        self.release_store.initialise()

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

    @property
    def image_repositories(self):
        """
        Gets all the image repositories in the config, keyed by ID.

        Every repository will have the following keys:

        -   account_id
        -   region_name
        -   role_arn
        -   repository_name
        -   services

        """
        result = {}

        for repo in self.config.get("image_repositories", []):
            namespace = repo.get("namespace", self.namespace)

            # We should have uniqueness by the checks in prepare_config(), but
            # it doesn't hurt to check.
            assert repo["id"] not in result, repo["id"]

            result[repo["id"]] = {
                "account_id": repo.get("account_id", self.account_id),
                "region_name": repo.get("region_name", self.region_name),
                "role_arn": repo.get("role_arn", self.role_arn),
                "repository_name": f"{namespace}/{repo['id']}",
                "services": repo.get("services", []),
            }

        assert len(result) == len(self.config.get("image_repositories", []))
        return result

    @property
    def environment_names(self):
        result = {}

        for env in self.config.get("environments", []):

            # We should have uniqueness by the checks in prepare_config(), but
            # it doesn't hurt to check.
            assert env["id"] not in result

            assert set(env.keys()) == {"id", "name"}
            result[env["id"]] = env["name"]

        assert len(result) == len(self.config.get("environments", []))
        return result

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
            "requested_by": iam.get_underlying_role_arn(),
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

    def _get_services_by_image_id(self, release):
        """
        Generates a set of tuples (image_id, List[services])
        """
        for image_id in release["images"]:
            try:
                matched_image = self.image_repositories[image_id]
            except KeyError:
                continue

            yield (image_id, matched_image["services"])

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
            try:
                matched_image = self.image_repositories[image_id]
            except KeyError:
                continue

            available_services = []

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
        matched_image = self.image_repositories[image_id]

        # Create an ECR client for the correct account
        ecr = self._ecr(matched_image["account_id"])

        ecr.login()

        remote_uri, remote_tag, local_tag = ecr.publish_image(
            namespace=matched_image["namespace"],
            image_id=image_id,
        )

        tag_result = ecr.tag_image(
            namespace=matched_image["namespace"],
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
            image_repositories=self.image_repositories,
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
        previous_release = self.release_store.get_latest_release()

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

        try:
            matched_image = self.image_repositories[image_id]
            ecr = self._ecr(
                account_id=matched_image["account_id"],
                region_name=matched_image["region_name"],
                role_arn=matched_image["role_arn"],
            )
        except KeyError:
            # TODO: Does it make sense to create an ECR client if we don't
            # have an ECR repo to tag in?
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
