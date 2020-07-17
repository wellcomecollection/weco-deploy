import datetime

import yaml

from .ecr import Ecr
from .ecs import Ecs

from .releases_store import DynamoDbReleaseStore
from .parameter_store import SsmParameterStore
from .iam import Iam


class Projects:
    @staticmethod
    def _load(project_filepath):
        with open(project_filepath) as infile:
            return yaml.safe_load(infile)

    def __init__(self, project_filepath):
        self.projects = Projects._load(project_filepath)

    def list(self):
        return list(self.projects.keys())

    def load(self, project_id, region_name=None, role_arn=None, account_id=None):
        config = self.projects.get(project_id)

        if not config:
            raise RuntimeError(f"No matching project {project_id} in {self.projects()}")

        return Project(project_id, config, region_name, role_arn, account_id)


class Project:
    def __init__(self, project_id, config, region_name=None, role_arn=None, account_id=None):
        self.id = project_id
        self.config = config

        self.config['id'] = project_id

        if role_arn:
            self.config['role_arn'] = role_arn

        if region_name:
            self.config['aws_region_name'] = region_name

        iam = Iam(
            self.config['role_arn'],
            self.config['aws_region_name']
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
        self.region_name = self.config['aws_region_name']
        self.account_id = self.config['account_id']

        # Create required services
        self.releases_store = DynamoDbReleaseStore(
            project_id=self.id,
            region_name=self.region_name,
            role_arn=self.role_arn
        )

        self.parameter_store = SsmParameterStore(
            project_id=self.id,
            region_name=self.region_name,
            role_arn=self.role_arn
        )

        self.ecr = Ecr(
            account_id=self.account_id,
            region_name=self.region_name,
            role_arn=self.role_arn
        )

        self.ecs = Ecs(
            account_id=self.account_id,
            region_name=self.region_name,
            role_arn=self.role_arn
        )

        # Ensure release store is available
        self.releases_store.initialise()

    def _create_deployment(self, environment_id, details, description):
        return {
            "environment": environment_id,
            "date_created": datetime.datetime.utcnow().isoformat(),
            "requested_by": self.user_details['caller_identity']['arn'],
            "description": description,
            "details": details
        }

    def get_environment(self, environment_id):
        environments = {
            e['id']: e for e in self.config['environments'] if 'id' in e
        }

        if environment_id not in environments:
            raise ValueError(f"Unknown environment. Expected '{environment_id}' in {environments}")

        return environments[environment_id]

    def get_release(self, release_id):
        if release_id == "latest":
            return self.releases_store.get_latest_release()
        else:
            return self.releases_store.get_release(release_id)

    def get_ecs_services(self, release_id, environment_id):
        release = self.get_release(release_id)

        matched_services = {}
        for image_id, image_uri in release['images'].items():
            image_repositories = self.config.get('image_repositories')

            # Naively assume service name matches image id
            service_ids = [image_id]

            # Attempt to match deployment image id to config and override service_ids
            if image_repositories:
                matched_image_ids = [image for image in image_repositories if image['id'] == image_id]

                if matched_image_ids:
                    matched_image_id = matched_image_ids[0]
                    service_ids = matched_image_id.get('services')

            # Attempt to match service ids to ECS services
            available_services = [self.ecs.get_service(service_id, environment_id) for service_id in service_ids]
            available_services = [service for service in available_services if service]

            if available_services:
                matched_services[image_id] = available_services

        return matched_services

    def deploy(self, release_id, environment_id, namespace, description):
        release = self.get_release(release_id)
        matched_services = self.get_ecs_services(release_id, environment_id)

        # Force check for valid environment
        _ = self.get_environment(environment_id)

        deployment_details = {}
        for image_id, image_name in release['images'].items():
            ssm_result = self.parameter_store.update_ssm(
                service_id=image_id,
                label=environment_id,
                image_name=image_name
            )

            old_tag = image_name.split(":")[-1]
            new_tag = f"env.{environment_id}"

            tag_result = self.ecr.tag_image(
                namespace=namespace,
                service_id=image_id,
                tag=old_tag,
                new_tag=new_tag
            )

            ecs_deployments = []
            if image_id in matched_services:
                deployments = [self.ecs.redeploy_service(
                    service['clusterArn'],
                    service['serviceArn']
                ) for service in matched_services.get(image_id)]

                for deployment in deployments:
                    service_arn = deployment['service_arn']
                    deployment_id = deployment['deployment_id']
                    ecs_deployments.append({
                        'service_arn': service_arn,
                        'deployment_id': deployment_id
                    })

            deployment_details[image_id] = {
                'ssm_result': ssm_result,
                'tag_result': tag_result,
                'ecs_deployments': ecs_deployments
            }

        deployment = self._create_deployment(environment_id, deployment_details, description)

        self.releases_store.add_deployment(release['release_id'], deployment)

        return deployment


