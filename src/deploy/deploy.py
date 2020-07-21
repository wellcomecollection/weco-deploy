import click
import json

from dateutil.parser import parse
from pprint import pprint
from tabulate import tabulate

from . import git
from .pretty_printing import pprint_date
from .project import Projects

DEFAULT_PROJECT_FILEPATH = ".wellcome_project"
DEFAULT_ECR_NAMESPACE = "uk.ac.wellcome"


def _format_ecr_uri(uri):
    image_name = uri.split("/")[2]
    image_label, image_tag = image_name.split(":")

    return {
        'label': image_label,
        'tag': image_tag
    }


def _summarise_ssm_response(images):
    for image in images:
        yield {
            'name': image['Name'],
            'value': image['Value'],
            'last_modified': image['LastModifiedDate'].strftime('%d-%m-%YT%H:%M')
        }


def _summarise_release_deployments(releases):
    for release in releases:
        for deployment in release['deployments']:
            try:
                requested_by = deployment.get("requested_by", {}).get("id", "")
            except AttributeError:
                requested_by = deployment.get("requested_by", "")

            yield {
                'release_id': release.get('release_id'),
                'environment_id': deployment.get('environment'),
                'deployed_date': parse(deployment.get('date_created')),
                'requested_by': requested_by.split('/')[-1],
                'description': deployment.get('description')
            }


@click.group()
@click.option('--project-file', '-f', default=DEFAULT_PROJECT_FILEPATH)
@click.option('--verbose', '-v', is_flag=True, help="Print verbose messages.")
@click.option('--confirm', '-y', is_flag=True, help="Non-interactive deployment confirmation")
@click.option("--project-id", '-i', help="Specify the project ID")
@click.option("--region-name", '-i', help="Specify the AWS region name")
@click.option("--account-id", help="Specify the AWS account ID")
@click.option("--role-arn", help="Specify an AWS role to assume")
@click.option('--dry-run', '-d', is_flag=True, help="Don't make changes.")
@click.pass_context
def cli(ctx, project_file, verbose, confirm, project_id, region_name, account_id, role_arn, dry_run):
    try:
        projects = Projects(project_file)
    except FileNotFoundError:
        if ctx.invoked_subcommand != "initialise":
            message = f"Couldn't find project metadata file {project_file!r}.  Run `initialise`."
            raise click.UsageError(message) from None
        ctx.obj = {
            'project_filepath': project_file,
            'verbose': verbose,
            'dry_run': dry_run,
        }
        return

    project_names = projects.list()
    project_count = len(project_names)

    if not project_id:
        if project_count == 1:
            project_id = project_names[0]
        else:
            project_id = click.prompt(
                text="Enter the project ID",
                type=click.Choice(project_names)
            )

    project = projects.load(
        project_id=project_id,
        region_name=region_name,
        account_id=account_id,
        role_arn=role_arn
    )

    config = project.config

    user_arn = project.user_details['caller_identity']['arn']
    underlying_user_arn = project.user_details['underlying_caller_identity']['arn']

    if verbose:
        click.echo(click.style(f"Loaded {project_file}:", fg="cyan"))
        pprint(config)
        click.echo("")
        click.echo(click.style(f"Using role_arn:         {config['role_arn']}", fg="cyan"))
        click.echo(click.style(f"Using aws_region_name:  {config['aws_region_name']}", fg="cyan"))
        click.echo(click.style(f"Running as role:        {user_arn}", fg="cyan"))
        if user_arn != underlying_user_arn:
            click.echo(click.style(f"Underlying role:        {underlying_user_arn}", fg="cyan"))

        click.echo(click.style(f"Using account_id:       {config['account_id']}", fg="cyan"))
        click.echo("")

    ctx.obj = {
        'project_filepath': project_file,
        'verbose': verbose,
        'confirm': confirm,
        'dry_run': dry_run,
        'project': project
    }


def _publish(project, image_id, namespace, label):
    click.echo(click.style(f"Attempting to publish {project.id}/{image_id}", fg="green"))

    publish_result = project.publish(
        namespace=namespace,
        image_id=image_id,
        label=label
    )

    ssm_path = publish_result['ssm_update']['ssm_path']
    ssm_value = publish_result['ssm_update']['image_name']
    local_tag = publish_result['ecr_push']['local_tag']
    remote_uri = publish_result['ecr_push']['remote_uri']
    tag_source = publish_result['ecr_tag']['source']
    tag_target = publish_result['ecr_tag']['target']

    click.echo(click.style(f"Published {local_tag} to {remote_uri}", fg="yellow"))
    click.echo(click.style(f"Tagged {tag_source} with {tag_target}", fg="yellow"))
    click.echo(click.style(f"Updated SSM path {ssm_path} to {ssm_value}", fg="yellow"))

    click.echo(click.style(f"Done publishing {project.id}/{image_id}", fg="bright_green"))


@cli.command()
@click.option("--image-id", required=True)
@click.option("--namespace", required=True, default=DEFAULT_ECR_NAMESPACE)
@click.option("--label", default="latest")
@click.pass_context
def publish(ctx, image_id, namespace, label):
    project = ctx.obj['project']

    _publish(
        project=project,
        image_id=image_id,
        namespace=namespace,
        label=label
    )


def _deploy(project, release_id, environment_id, namespace, description, confirm=True):
    release = project.get_release(release_id)

    environment = project.get_environment(environment_id)
    env_id = environment.get('id')
    env_name = environment.get('name', environment_id)

    click.echo("")
    click.echo(click.style(f"Deploying release {release['release_id']}", fg="green"))
    click.echo(click.style(f"Targeting env: {env_id}, ({env_name})", fg="yellow"))
    click.echo(click.style(f"Requested by: {release['requested_by']}", fg="yellow"))
    click.echo(click.style(f"Date created: {release['date_created']}", fg="yellow"))

    ecs_services = project.get_ecs_services(release_id, environment_id)

    for image_id, services in ecs_services.items():
        service_arns = [service['serviceArn'] for service in services]
        click.echo(click.style(f"{image_id}: ECS Services discovered: {service_arns}", fg="bright_yellow"))

    if not confirm:
        click.echo("")
        click.confirm(click.style("Create deployment?", fg="cyan", bold=True), abort=True)

    result = project.deploy(release_id, environment_id, namespace, description)

    click.echo("")
    click.echo(click.style("Deployment Summary", fg="green"))
    click.echo(click.style(f"Requested by: {result['requested_by']}", fg="yellow"))
    click.echo(click.style(f"Date created: {result['date_created']}", fg="yellow"))
    click.echo("")
    for image_id, summary in result['details'].items():
        click.echo(click.style(f"Summary for {image_id}", fg="bright_yellow"))
        click.echo(click.style(
            f"{image_id}: SSM Updated {summary['ssm_result']['ssm_path']} to {summary['ssm_result']['image_name']}",
            fg="yellow"
        ))
        click.echo(click.style(
            f"{image_id}: ECR Updated {summary['tag_result']['source']} to {summary['tag_result']['target']}",
            fg="yellow"
        ))

        for ecs_deployment in summary['ecs_deployments']:
            click.echo(click.style(
                f"{image_id}: ECS Deployed {ecs_deployment['service_arn']} to {ecs_deployment['deployment_id']}",
                fg="yellow"
            ))

    click.echo("")
    click.echo(click.style(f"Deployed release {release['release_id']} to {env_id}, ({env_name})", fg="bright_green"))


@cli.command()
@click.option('--release-id', prompt="Release ID to deploy", default="latest", show_default=True,
              help="The ID of the release to be deployed, or the latest release if unspecified")
@click.option('--environment-id', prompt="Environment ID to deploy release to",
              default="stage", show_default=True,
              help="The target environment of this deployment")
@click.option("--namespace", default=DEFAULT_ECR_NAMESPACE, show_default=True)
@click.option('--description', prompt="Enter a description for this deployment",
              help="A description of this deployment", default="No description provided")
@click.pass_context
def deploy(ctx, release_id, environment_id, namespace, description):
    confirm = ctx.obj['confirm']
    project = ctx.obj['project']

    _deploy(
        project=project,
        release_id=release_id,
        environment_id=environment_id,
        namespace=namespace,
        description=description,
        confirm=confirm
    )


def _prepare(project, from_label, namespace, description):
    release = project.prepare(
        from_label=from_label,
        namespace=namespace,
        description=description
    )

    prev_release = release["previous_release"]
    new_release = release["new_release"]

    click.echo(click.style(f"Prepared release from images in {from_label}", fg="green"))
    click.echo(click.style(f"Requested by: {new_release['requested_by']}", fg="yellow"))
    click.echo(click.style(f"Date created: {new_release['date_created']}", fg="yellow"))
    click.echo("")

    rows = []

    headers = [
        "service",
        "old image",
        "new image",
        "Git commit",
    ]

    for service, image in sorted(new_release["images"].items()):
        # The image IDs are of the form
        #
        #     {ecr_repo_uri}/{namespace}/{service}:ref.{git_commit}
        #
        prev_git_commit = prev_release["images"].get(service, "").split(".")[-1][:7]
        new_git_commit = image.split(".")[-1][:7]

        rows.append([
            service,
            prev_git_commit,
            new_git_commit
            if new_git_commit == prev_git_commit
            else click.style(new_git_commit, fg="green"),
            git.log(new_git_commit),
        ])

    print(tabulate(rows, headers=headers))

    click.echo("")
    click.echo(click.style(f"Created release {new_release['release_id']}", fg="bright_green"))

    return new_release['release_id']


@cli.command()
@click.option('--from-label', prompt="Label to base release upon",
              help="The existing label upon which this release will be based",
              default="latest", show_default=True)
@click.option('--namespace', help="Namespace in which to locate images",
              default=DEFAULT_ECR_NAMESPACE)
@click.option('--description', prompt="Description for this release",
              default="No description provided")
@click.pass_context
def prepare(ctx, from_label, namespace, description):
    project = ctx.obj['project']

    _prepare(
        project=project,
        from_label=from_label,
        namespace=namespace,
        description=description
    )


@cli.command()
@click.option('--from-label', prompt="Label to base release upon",
              help="The existing label upon which this release will be based", default="latest", show_default=True)
@click.option('--environment-id', prompt="Environment ID to deploy release to",
              default="stage", show_default=True,
              help="The target environment of this deployment")
@click.option("--namespace", default=DEFAULT_ECR_NAMESPACE, show_default=True)
@click.option('--description', prompt="Enter a description for this deployment",
              help="A description of this deployment", default="No description provided")
@click.pass_context
def release_deploy(ctx, from_label, environment_id, namespace, description):
    project = ctx.obj['project']
    confirm = ctx.obj['confirm']

    release_id = _prepare(
        project=project,
        from_label=from_label,
        namespace=namespace,
        description=description
    )

    _deploy(
        project=project,
        release_id=release_id,
        environment_id=environment_id,
        namespace=namespace,
        description=description,
        confirm=confirm
    )


@cli.command()
@click.argument('release_id', required=False)
@click.pass_context
def show_release(ctx, release_id):
    project = ctx.obj['project']

    if not release_id:
        release_id = 'latest'

    release = project.get_release(release_id)

    click.echo(json.dumps(release, sort_keys=True, indent=2))


@cli.command()
@click.argument('release_id', required=False)
@click.pass_context
def show_deployments(ctx, release_id):
    project = ctx.obj['project']

    releases = project.get_deployments(release_id)

    rows = []

    headers = [
        "release ID",
        "environment ID",
        "deployed date",
        "request by",
        "description"
    ]

    for summary in _summarise_release_deployments(releases):
        try:
            environment_id = summary["environment_id"].get("id", "")
        except AttributeError:
            environment_id = summary["environment_id"]

        rows.append([
            summary["release_id"],
            environment_id,
            pprint_date(summary["deployed_date"]),
            summary["requested_by"],
            summary["description"]
        ])

    print(tabulate(rows, headers=headers))


@cli.command()
@click.option('--label', '-l', help="The label to show (e.g., latest')")
@click.pass_context
def show_images(ctx, label):
    project = ctx.obj['project']

    if not label:
        label = 'latest'

    images = project.get_images(label)

    rows = []

    headers = [
        "image ID",
        "label",
        "tag",
    ]

    for image_id, ecr_uri in images.items():
        ecr_uri = _format_ecr_uri(ecr_uri)
        rows.append([image_id, ecr_uri["label"], ecr_uri["tag"]])

    print(tabulate(rows, headers=headers))


def main():
    cli()
