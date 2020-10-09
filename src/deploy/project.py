import datetime
from urllib.parse import urlparse
import uuid

import yaml

from .ecr import Ecr
from .ecs import Ecs

from .releases_store import DynamoDbReleaseStore
from .iam import Iam

DEFAULT_ECR_NAMESPACE = "uk.ac.wellcome"
DEFAULT_REGION_NAME = "eu-west-1"


def _is_url(label):
    try:
        res = urlparse(label)
        return all([res.scheme, res.netloc])
    except ValueError:
        return False


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
            raise RuntimeError(f"No matching project {project_id} in {self.projects}")

        return Project(project_id=project_id, config=config, **kwargs)


class Project:
    def __init__(self, project_id, config, region_name=None, role_arn=None, account_id=None, namespace=None):
        self.id = project_id
        self.config = config

        self.config['id'] = project_id

        if namespace:
            self.config['namespace'] = namespace
        else:
            if 'namespace' not in self.config:
                self.config['namespace'] = DEFAULT_ECR_NAMESPACE

        if role_arn:
            self.config['role_arn'] = role_arn
        else:
            if 'role_arn' not in self.config:
                raise ValueError("region_name is not set!")

        if region_name:
            self.config['region_name'] = region_name
        else:
            if 'region_name' not in self.config:
                self.config['region_name'] = DEFAULT_REGION_NAME

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
        self.role_arn = self.config['role_arn']
        self.region_name = self.config['region_name']
        self.account_id = self.config['account_id']
        self.namespace = self.config['namespace']
        self.image_repositories = self.config.get('image_repositories', [])

        # Create required services
        self.releases_store = DynamoDbReleaseStore(
            project_id=self.id,
            region_name=self.region_name,
            role_arn=self.role_arn
        )

        self.prepared_releases = {}

        # Ensure release store is available
        self.releases_store.initialise()

    def _ecr(self, account_id=None, region_name=None, role_arn=None):
        return Ecr(
            account_id=account_id or self.account_id,
            region_name=region_name or self.region_name,
            role_arn=role_arn or self.role_arn
        )

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
        for image_id, image_uri in release['images'].items():
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
        release_images = {}
        for image in self.image_repositories:

            image_id = image['id']

            image_details = self._ecr(
                account_id=image.get('account_id'),
                region_name=image.get('region_name'),
                role_arn=image.get('role_arn')
            ).describe_image(
                namespace=image.get('namespace', self.namespace),
                image_id=image_id,
                tag=from_label,
                account_id=image.get('account_id')
            )

            release_images[image_details['image_id']] = image_details['ref']

        return release_images

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
