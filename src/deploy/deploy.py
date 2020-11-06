import click
import datetime
import json
import os
import sys
import time

from dateutil.parser import parse
from pprint import pprint
from tabulate import tabulate

from . import git, iam
from .pretty_printing import pprint_date
from .project import Projects

DEFAULT_PROJECT_FILEPATH = ".wellcome_project"

LOGGING_ROOT = os.path.join(os.environ["HOME"], ".local", "share", "weco-deploy")


@click.group()
@click.option('--project-file', '-f', default=DEFAULT_PROJECT_FILEPATH)
@click.option('--verbose', '-v', is_flag=True, help="Print verbose messages.")
@click.option('--confirm', '-y', is_flag=True, help="Non-interactive deployment confirmation")
@click.option("--project-id", '-i', help="Specify the project ID")
@click.option("--region-name", '-i', help="Specify the AWS region name")
@click.option("--account-id", help="Specify the AWS account ID")
@click.option("--namespace", help="Specify the project namespace")
@click.option("--role-arn", help="Specify an AWS role to assume")
@click.option('--dry-run', '-d', is_flag=True, help="Don't make changes.")
@click.pass_context
def cli(ctx, project_file, verbose, confirm, project_id, region_name, account_id, namespace, role_arn, dry_run):
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
        role_arn=role_arn,
        account_id=account_id,
        namespace=namespace
    )

    config = project.config

    user_arn = project.role_arn
    underlying_user_arn = iam.get_underlying_role_arn()

    if verbose:
        click.echo(click.style(f"Loaded {project_file}:", fg="cyan"))
        pprint(config)
        click.echo("")

        lines = [
            f"Using role ARN:   {config['role_arn']}",
            f"IN region:        {config['region_name']}",
            f"Running as role:  {user_arn}",
            f"Underlying role:  {underlying_user_arn}" if user_arn != underlying_user_arn else "",
            f"Using account ID: {config['account_id']}"
        ]

        message = "\n".join([ln for ln in lines if ln])
        click.echo(click.style(message, fg="cyan"))
        click.echo("")

    ctx.obj = {
        'project_filepath': project_file,
        'verbose': verbose,
        'confirm': confirm,
        'dry_run': dry_run,
        'project': project
    }


def _publish(project, image_id, label):
    click.echo(click.style(f"Attempting to publish {project.id}/{image_id}", fg="green"))

    publish_result = project.publish(
        image_id=image_id,
        label=label
    )

    local_tag = publish_result['ecr_push']['local_tag']
    remote_uri = publish_result['ecr_push']['remote_uri']
    tag_source = publish_result['ecr_tag']['source']
    tag_target = publish_result['ecr_tag']['target']

    click.echo(click.style(f"Published {local_tag} to {remote_uri}", fg="yellow"))
    click.echo(click.style(f"Tagged {tag_source} with {tag_target}", fg="yellow"))

    click.echo(click.style(f"Done publishing {project.id}/{image_id}", fg="bright_green"))


@cli.command()
@click.option("--image-id", required=True)
@click.option("--label", default="latest")
@click.pass_context
def publish(ctx, image_id, label):
    project = ctx.obj['project']

    _publish(
        project=project,
        image_id=image_id,
        label=label
    )


def save_deployment(deployment_result):
    """
    Save the result of the deployment to a file, including things like
    the ECS deploy IDs.  These can be useful for debugging if something goes wrong.

    Returns the path to the saved file.
    """
    out_path = os.path.join(
        LOGGING_ROOT, "deployment_results",
        datetime.datetime.now().strftime('deploy_%Y-%m-%d_%H-%M-%S.json')
    )

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as out_file:
        out_file.write(json.dumps(deployment_result, indent=2, sort_keys=True))

    return out_path


def _deploy(project, release, environment_id, description, confirm=True):
    environment_name = project.environment_names[environment_id]

    click.echo("")
    click.echo(click.style(f"Deploying release {release['release_id']}", fg="green"))
    click.echo(click.style(f"Targeting env: {environment_id} ({environment_name})", fg="yellow"))
    click.echo(click.style(f"Requested by: {release['requested_by']}", fg="yellow"))
    click.echo(click.style(f"Date created: {release['date_created']}", fg="yellow"))

    ecs_service_arns = project.get_ecs_service_arns(
        release=release,
        environment_id=environment_id
    )

    rows = []

    headers = ["image ID", "services"]

    for image_id, service_arns in sorted(ecs_service_arns.items()):
        names = [
            click.style(arn.split("/")[-1], fg="green")
            for arn in service_arns
        ]
        rows.append([image_id, "\n".join(sorted(names))])

    click.echo("")
    click.echo(click.style("ECS services discovered:\n", fg="yellow", underline=True))
    click.echo(tabulate(rows, headers=headers))

    if not confirm:
        click.echo("")
        click.confirm(click.style("Create deployment?", fg="cyan", bold=True), abort=True)

    result = project.deploy(release["release_id"], environment_id, description)

    out_path = save_deployment(result)

    click.echo("")
    click.echo(click.style("Deployment Summary", fg="green"))
    click.echo(click.style(f"Requested by: {result['requested_by']}", fg="yellow"))
    click.echo(click.style(f"Date created: {result['date_created']}", fg="yellow"))
    click.echo(click.style(f"Deploy data:  {out_path}", fg="yellow"))
    click.echo("")

    rows = []

    headers = ['image ID', 'summary of changes']
    for image_id, summary in result['details'].items():
        if summary['tag_result']['status'] == 'success':
            ecr_display = 'ECR tag updated'
        else:
            ecr_display = ''

        if not summary['ecs_deployments']:
            ecs_display = ''
        elif len(summary['ecs_deployments']) == 1:
            ecs_display = '1 service deployed'
        else:
            ecs_display = '%d services deployed' % len(summary['ecs_deployments'])

        if not ecr_display and not ecs_display:
            rows.append([image_id, '-'])
        elif not ecr_display:
            rows.append([image_id, ecs_display])
        else:
            rows.append([image_id, ', '.join([ecr_display, ecs_display])])

    click.echo(tabulate(rows, headers=headers))

    click.echo("")
    click.echo(click.style(f"Deployed release {release['release_id']} to {environment_id} ({environment_name})", fg="bright_green"))


@cli.command()
@click.option('--release-id', prompt="Release ID to deploy", default="latest", show_default=True,
              help="The ID of the release to be deployed, or the latest release if unspecified")
@click.option('--environment-id', prompt="Environment ID to deploy release to",
              default="stage", show_default=True,
              help="The target environment of this deployment")
@click.option('--description', prompt="Enter a description for this deployment",
              help="A description of this deployment", default="No description provided")
@click.option('--confirmation-wait-for',
              help="How many seconds to wait for a confirmation for", default=600,
              show_default=True)
@click.option('--confirmation-interval',
              help="How many seconds in an interval before re-confirming a deploy", default=10,
              show_default=True)
@click.pass_context
def deploy(ctx, release_id, environment_id, description, confirmation_wait_for, confirmation_interval):
    confirm = ctx.obj['confirm']
    project = ctx.obj['project']

    release = project.get_release(release_id)

    _deploy(
        project=project,
        release=release,
        environment_id=environment_id,
        description=description,
        confirm=confirm
    )

    _confirm_deploy(
        project=project,
        release=release,
        environment_id=environment_id,
        wait_for_seconds=confirmation_wait_for,
        interval=confirmation_interval
    )


def _confirm_deploy(project, release, environment_id, wait_for_seconds, interval):
    total_time_waited = 0
    start_timer = time.perf_counter()

    release_id = release["release_id"]

    click.echo("")
    click.echo(click.style(f"Checking deployment of {release_id} to {environment_id}", fg="yellow"))
    click.echo(click.style(f"Allowing {wait_for_seconds}s for deployment.", fg="yellow"))

    while not project.is_release_deployed(release, environment_id):
        total_time_waited = int(time.perf_counter() - start_timer)

        exceeded_wait_time = total_time_waited >= wait_for_seconds

        if exceeded_wait_time:
            click.echo("")
            click.echo(click.style(f"Deployment of {release_id} to {environment_id} failed", fg="red"))
            click.echo(click.style(f"Deployment time exceeded {wait_for_seconds}s", fg="red"))
            sys.exit(1)

        retry_message = f"Trying again in {interval}s (waited {total_time_waited}s)."
        click.echo(click.style(retry_message, fg="yellow"))

        time.sleep(interval)

    total_time_waited = int(time.perf_counter() - start_timer)

    click.echo("")
    click.echo(click.style(f"Deployment of {release_id} to {environment_id} successful", fg="bright_green"))
    click.echo(click.style(f"Deployment took {total_time_waited}s", fg="bright_green"))
    sys.exit(0)


def _display_release(release, from_label):
    prev_release = release["previous_release"]
    new_release = release["new_release"]

    click.echo(click.style(f"Prepared release from images in {from_label}", fg="green"))
    if prev_release is None:
        click.echo(click.style("This is your first release for this project!", fg="yellow"))
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
        prev_git_commit = "-------"
        if prev_release is not None:
            prev_git_commit = prev_release["images"].get(service, "").split(".")[-1][:7]

        new_git_commit = image.split(".")[-1][:7]

        rows.append([
            service,
            prev_git_commit,
            "-" if new_git_commit == prev_git_commit else new_git_commit,
            "-" if new_git_commit == prev_git_commit else git.log(new_git_commit),
        ])

    click.echo(tabulate(rows, headers=headers))

    click.echo("")
    click.echo(click.style(f"Created release {new_release['release_id']}", fg="bright_green"))

    return new_release['release_id']


def _prepare(project, from_label, description):
    release = project.prepare(
        from_label=from_label,
        description=description
    )

    _display_release(
        release=release,
        from_label=from_label
    )

    return release["new_release"]


@cli.command()
@click.option('--from-label', prompt="Label to base release upon",
              help="The existing label upon which this release will be based",
              default="latest", show_default=True)
@click.option('--description', prompt="Description for this release",
              default="No description provided")
@click.pass_context
def prepare(ctx, from_label, description):
    project = ctx.obj['project']

    _prepare(
        project=project,
        from_label=from_label,
        description=description
    )


def _update(project, release_id, service_ids, from_label):
    release = project.update(
        release_id=release_id,
        service_ids=service_ids,
        from_label=from_label
    )

    _display_release(
        release=release,
        from_label=from_label
    )

    return release["new_release"]


@cli.command()
@click.option('--release-id', prompt="Release ID to deploy", default="latest", show_default=True,
              help="The release ID from which to create a new release")
@click.option('--service-ids', prompt="Comma separated list of Service IDs",
              help="The services which will be updated")
@click.option('--from-label', prompt="Label to base release upon",
              help="The existing label from which to update specified services",
              default="latest", show_default=True)
@click.pass_context
def update(ctx, release_id, service_ids, from_label):
    project = ctx.obj['project']

    _update(
        project=project,
        release_id=release_id,
        service_ids=service_ids.split(","),
        from_label=from_label,
    )


@cli.command()
@click.option('--from-label', prompt="Label to base release upon",
              help="The existing label upon which this release will be based", default="latest", show_default=True)
@click.option('--environment-id', prompt="Environment ID to deploy release to",
              default="stage", show_default=True,
              help="The target environment of this deployment")
@click.option('--description', prompt="Enter a description for this deployment",
              help="A description of this deployment", default="No description provided")
@click.option('--confirmation-wait-for',
              help="How many seconds to wait for a confirmation for", default=600,
              show_default=True)
@click.option('--confirmation-interval',
              help="How many seconds in an interval before re-confirming a deploy", default=10,
              show_default=True)
@click.pass_context
def release_deploy(ctx, from_label, environment_id, description, confirmation_wait_for, confirmation_interval):
    project = ctx.obj['project']
    confirm = ctx.obj['confirm']

    release = _prepare(
        project=project,
        from_label=from_label,
        description=description
    )

    _deploy(
        project=project,
        release=release,
        environment_id=environment_id,
        description=description,
        confirm=confirm
    )

    _confirm_deploy(
        project=project,
        release=release,
        environment_id=environment_id,
        wait_for_seconds=confirmation_wait_for,
        interval=confirmation_interval
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
@click.option('--environment-id', required=False)
@click.option('--limit', required=False, default=10)
@click.pass_context
def show_deployments(ctx, release_id, environment_id, limit):
    project = ctx.obj['project']

    rows = []

    headers = [
        "release ID",
        "environment ID",
        "deployed date",
        "request by",
        "description"
    ]

    for deployment in project.get_deployments(
        release_id=release_id,
        environment_id=environment_id,
        limit=limit
    ):
        rows.append(
            [
                deployment["release_id"],
                deployment["environment"],
                pprint_date(parse(deployment["date_created"])),
                deployment["requested_by"].split("/")[-1],
                deployment["description"]
                if deployment["description"] != "No description provided"
                else "-",
            ]
        )

    print(tabulate(rows, headers=headers))


@cli.command()
@click.option("--label", help="The label to show", default="latest", show_default=True)
@click.pass_context
def show_images(ctx, label):
    project = ctx.obj['project']

    images = project.get_images(label)

    rows = []

    headers = [
        "image ID",
        "label",
        "tag",
    ]

    for image_id, ref_tag in images.items():
        if ref_tag:
            rows.append([image_id, label, ref_tag])
        else:
            rows.append([image_id, "-", "-"])

    print(tabulate(rows, headers=headers))


def main():
    cli()
