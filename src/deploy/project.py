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

    # def deploy(self, release_id, environment_id, namespace, description):
    #     if release_id == "latest":
    #         release = self.releases_store.get_latest_release()
    #     else:
    #         release = self.releases_store.get_release(release_id)
    #
    #
    #     for image_id, image_name in release['images'].items():
    #         ssm_path = parameter_store.update_ssm(
    #             service_id=image_id,
    #             label=environment_id,
    #             image_name=image_name,
    #             dry_run=dry_run
    #         )
    #
    #     click.echo(click.style(f"{image_id}: Updated SSM path {ssm_path} to {image_name}", fg="bright_yellow"))
    #
    #     old_tag = image_name.split(":")[-1]
    #     new_tag = f"env.{environment_id}"
    #
    #     result = ecr.retag_image(
    #         namespace=namespace,
    #         service_id=image_id,
    #         tag=old_tag,
    #         new_tag=new_tag,
    #         dry_run=dry_run
    #     )
    #
    #     if result['status'] == 'success':
    #         click.echo(click.style(
    #             f"{image_id}: Re-tagged image {image_id}:{old_tag} to {image_id}:{new_tag}",
    #             fg="bright_yellow"
    #         ))
    #     else:
    #         click.echo(click.style(
    #             f"{image_id}: Already tagged image {image_id}:{old_tag} to {image_id}:{new_tag} (nothing to do)",
    #             fg="yellow"
    #         ))
    #
    #     if image_id in matched_services:
    #         deployments = [ecs.redeploy_service(
    #             service['clusterArn'],
    #             service['serviceArn']
    #         ) for service in matched_services.get(image_id)]
    #
    #         for deployment in deployments:
    #             service_arn = deployment['service_arn']
    #             deployment_id = deployment['deployment_id']
    #             click.echo(click.style(
    #                 f"{image_id}: ECS Service deployed {service_arn} to {deployment_id}",
    #                 fg="bright_yellow"
    #             ))