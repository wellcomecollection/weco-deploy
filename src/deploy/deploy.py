import click

from .commands import configure_aws_profile
from .publish import ecr_login, publish_image, update_ssm


@click.group()
def cli():
    pass


@click.command()
@click.option("--project_id", required=True)
@click.option("--service_id", required=True)
@click.option("--account_id", required=True)
@click.option("--region_id", required=True)
@click.option("--namespace", required=True)
@click.option("--label", default="latest")
@click.option("--role_arn")
def publish(project_id, service_id, account_id, region_id, namespace, label, role_arn):  # noqa: E501
    print(f"*** Attempting to publish {project_id}/{service_id}")

    profile_name = None
    if role_arn:
        profile_name = 'service_publisher'
        configure_aws_profile(role_arn, profile_name)

    ecr_login(account_id, profile_name)

    remote_image_name = publish_image(
        account_id,
        namespace,
        service_id,
        label,
        region_id
    )

    update_ssm(
        project_id,
        service_id,
        label,
        remote_image_name,
        profile_name
    )

    print(f"*** Done publishing {project_id}/{service_id}")


def main():
    cli.add_command(publish)
    cli()
