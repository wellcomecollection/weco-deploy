import click
import json

from dateutil.parser import parse
from urllib.parse import urlparse
from pprint import pprint

from .commands import configure_aws_profile
from .ecr import Ecr
from .model import create_deployment, create_release
from .project_config import load, save, exists, get_environments_lookup

from .releases_store import DynamoDbReleaseStore
from .parameter_store import SsmParameterStore
from .pretty_printing import pprint_path_keyval_dict
from .iam import Iam

DEFAULT_PROJECT_FILEPATH = ".wellcome_project"
DEFAULT_ECR_NAMESPACE = "uk.ac.wellcome"


def _format_ecr_uri(uri):
    image_name = uri.split("/")[2]
    image_label, image_tag = image_name.split(":")

    return {
        'label': image_label,
        'tag': image_tag[:7]
    }


def _summarise_ssm_response(images):
    for image in images:
        yield {
            'name': image['Name'],
            'value': image['Value'],
            'last_modified': image['LastModifiedDate'].strftime('%d-%m-%YT%H:%M')
        }


def _summarise_release_deployments(releases):
    summaries = []
    for r in releases:
        for d in r['deployments']:
            summaries.append(
                {
                    'release_id': r['release_id'][:8],
                    'environment_id': d['environment']['id'],
                    'deployed_date': parse(d['date_created']).strftime('%d-%m-%YT%H:%M'),
                    'description': d['description']
                }
            )
    return summaries


def _is_url(label):
    try:
        res = urlparse(label)
        return all([res.scheme, res.netloc])
    except ValueError:
        return False


@click.group()
@click.option('--project-file', '-f', default=DEFAULT_PROJECT_FILEPATH)
@click.option('--verbose', '-v', is_flag=True, help="Print verbose messages.")
@click.option("--project-id", '-i', help="Specify the project ID")
@click.option("--region-id", '-i', help="Specify the AWS region ID")
@click.option("--account-id", help="Specify the AWS account ID")
@click.option("--role-arn")
@click.option('--dry-run', '-d', is_flag=True, help="Don't make changes.")
@click.pass_context
def cli(ctx, project_file, verbose, project_id, region_id, account_id, role_arn, dry_run):
    try:
        projects = load(project_file)
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

    project_names = list(projects.keys())
    project_count = len(project_names)

    if not project_id:
        if project_count == 1:
            project_id = project_names[0]
        else:
            project_id = click.prompt(
                text="Enter the project ID",
                type=click.Choice(project_names)
            )

    project = projects.get(project_id)
    project['id'] = project_id

    if verbose and project:
        click.echo(f"Loaded {project_file} {project}")

    if role_arn:
        project['role_arn'] = role_arn
        if verbose:
            click.echo(f"Using role_arn {project['role_arn']}")

    if region_id:
        project['aws_region_name'] = region_id
        if verbose:
            click.echo(f"Using aws_region_name {project['aws_region_name']}")

    user_details = Iam(role_arn)
    caller_identity = user_details.caller_identity()
    underlying_caller_identity = user_details.caller_identity(underlying=True)

    if verbose:
        click.echo(f"Running as role {caller_identity['arn']}")
        if caller_identity['arn'] != underlying_caller_identity['arn']:
            click.echo(f"Underlying role {underlying_caller_identity['arn']}")
        click.echo("")

    if account_id:
        project['account_id'] = account_id
    else:
        project['account_id'] = caller_identity['account_id']

    if verbose:
        click.echo(f"Using account_id {project['account_id']}")

    ctx.obj = {
        'project_filepath': project_file,
        'role_arn': project.get('role_arn'),
        'github_repository': project.get('github_repository'),
        'tf_stack_root': project.get('tf_stack_root'),
        'verbose': verbose,
        'dry_run': dry_run,
        'project': project,
    }


@cli.command()
@click.option("--service-id", required=True)
@click.option("--namespace", required=True, default=DEFAULT_ECR_NAMESPACE)
@click.option("--label", default="latest")
@click.pass_context
def publish(ctx, service_id, namespace, label):
    project = ctx.obj['project']
    role_arn = ctx.obj['role_arn']
    dry_run = ctx.obj['dry_run']

    account_id = project['account_id']
    region_id = project['aws_region_name']

    ecr = Ecr(account_id, role_arn)
    parameter_store = SsmParameterStore(project['id'], role_arn)

    print(f"*** Attempting to publish {project['id']}/{service_id}")

    profile_name = None
    if role_arn:
        profile_name = 'service_publisher'
        configure_aws_profile(role_arn, profile_name)

    ecr.login(profile_name)

    remote_image_name = ecr.publish_image(
        namespace,
        service_id,
        label,
        region_id,
        dry_run
    )

    parameter_store.update_ssm(
        service_id,
        label,
        remote_image_name,
        dry_run
    )

    print(f"*** Done publishing {project['id']}/{service_id}")


@cli.command()
@click.option('--project-id', '-i', prompt="Enter an id for this project", help="The project ID")
@click.option('--project-name', '-n', prompt="Enter a descriptive name for this project",
              help="The name of the project")
@click.option('--environment-id', '-e', prompt="Enter an id for an environment", help="The primary environment's ID")
@click.option('--environment-name', '-a', prompt="Enter a descriptive name for this environment",
              help="The primary environment's name")
@click.pass_context
def initialise(ctx, project_id, project_name, environment_id, environment_name):
    role_arn = ctx.obj['role_arn']
    verbose = ctx.obj['verbose']
    dry_run = ctx.obj['dry_run']

    project_filepath = ctx.obj['project_filepath']

    releases_store = DynamoDbReleaseStore(project_id, role_arn)

    project = {
        'id': project_id,
        'name': project_name,
        'role_arn': role_arn,
        'environments': [
            {
                'id': environment_id,
                'name': environment_name
            }
        ]
    }

    if verbose:
        click.echo(pprint(project))
    if not dry_run:
        if exists(project_filepath):
            click.confirm(
                f"This will replace existing project file ({project_filepath}), do you want to continue?",
                abort=True)

        click.confirm(f"{releases_store.describe_initialisation()}?")
        releases_store.initialise()

        save(project_filepath, project)
    elif verbose:
        click.echo("dry-run, not created.")


@cli.command()
@click.option('--release-id', prompt="Release ID to deploy", default="latest", show_default=True,
              help="The ID of the release to be deployed, or the latest release if unspecified")
@click.option('--environment-id', prompt="Environment ID to deploy release to",
              help="The target environment of this deployment")
@click.option('--description', prompt="Enter a description for this deployment",
              help="A description of this deployment", default="No description given.")
@click.pass_context
def deploy(ctx, release_id, environment_id, description):
    project = ctx.obj['project']
    role_arn = ctx.obj['role_arn']
    dry_run = ctx.obj['dry_run']

    releases_store = DynamoDbReleaseStore(project['id'], role_arn)
    parameter_store = SsmParameterStore(project['id'], role_arn)
    user_details = Iam(role_arn)

    environments = get_environments_lookup(project)

    try:
        environment = environments[environment_id]
    except KeyError:
        raise ValueError(f"Unknown environment. Expected '{environment_id}' in {environments}")

    if release_id == "latest":
        release = releases_store.get_latest_release()
    else:
        release = releases_store.get_release(release_id)

    click.echo(click.style("Release to deploy:", fg="blue"))
    click.echo(pprint(release))
    click.confirm(click.style("create deployment?", fg="green", bold=True), abort=True)

    caller_identity = user_details.caller_identity(underlying=True)
    deployment = create_deployment(environment, caller_identity['arn'], description)

    click.echo(click.style("Created deployment:", fg="blue"))
    click.echo(pprint(deployment))

    if not dry_run:
        releases_store.add_deployment(release['release_id'], deployment)
        parameter_store.put_services_to_images(environment_id, release['images'])
    else:
        click.echo("dry-run, not created.")
        return


@cli.command()
@click.option('--from-label', prompt="Label to base release upon",
              help="The existing label upon which this release will be based", default="latest", show_default=True)
@click.option('--service-id', prompt="Service to update", default="all", show_default=True,
              help="The service to update with a (prompted for) new image")
@click.option('--release-description', prompt="Description for this release", default="No description given.")
@click.pass_context
def prepare(ctx, from_label, service_id, release_description):
    project = ctx.obj['project']
    role_arn = ctx.obj['role_arn']
    dry_run = ctx.obj['dry_run']

    releases_store = DynamoDbReleaseStore(project['id'], role_arn)
    parameter_store = SsmParameterStore(project['id'], role_arn)
    user_details = Iam(role_arn)

    from_images = parameter_store.get_services_to_images(from_label)
    service_source = "latest"
    if service_id == "all":
        release_image = {}
    else:
        service_source = click.prompt("Label or image URI to release for specified service", default="latest")
        if _is_url(service_source):
            release_image = {service_id: service_source}
        else:
            release_image = parameter_store.get_service_to_image(service_source, service_id)
    release_images = {**from_images, **release_image}

    if not release_images:
        raise click.UsageError(f"No images found for {project['id']} {service_id} {from_label}")

    caller_identity = user_details.caller_identity(underlying=True)

    release = create_release(
        project['id'],
        project['name'],
        caller_identity['arn'],
        release_description,
        release_images)

    if service_id == "all":
        click.echo(f"Prepared release from images in {from_label}")
    else:
        click.echo(f"Prepared release from images in {from_label} with {service_id} from {service_source}")
    click.echo(pprint(release))

    if not dry_run:
        releases_store.put_release(release)
    else:
        click.echo("dry-run, not created.")


@cli.command()
@click.argument('release_id', required=False)
@click.pass_context
def show_release(ctx, release_id):
    project = ctx.obj['project']
    role_arn = ctx.obj['role_arn']

    releases_store = DynamoDbReleaseStore(project['id'], role_arn)

    if not release_id:
        release = releases_store.get_latest_release()
    else:
        release = releases_store.get_release(release_id)
    click.echo(json.dumps(release, sort_keys=True, indent=2))


@cli.command()
@click.argument('release_id', required=False)
@click.pass_context
def show_deployments(ctx, release_id):
    project = ctx.obj['project']
    role_arn = ctx.obj['role_arn']

    releases_store = DynamoDbReleaseStore(project['id'], role_arn)

    if not release_id:
        releases = releases_store.get_recent_deployments()
    else:
        releases = [releases_store.get_release(release_id)]
    summaries = _summarise_release_deployments(releases)
    for summary in summaries:
        click.echo("{release_id} {environment_id} {deployed_date} '{description}'".format(**summary))


@cli.command()
@click.option('--label', '-l', help="The label to show (e.g., latest')")
@click.pass_context
def show_images(ctx, label):
    project = ctx.obj['project']
    role_arn = ctx.obj['role_arn']
    parameter_store = SsmParameterStore(project['id'], role_arn)

    images = parameter_store.get_images(label=label)

    summaries = sorted(_summarise_ssm_response(images), key=lambda k: k['name'])

    paths = {}
    for summary in summaries:
        result = {}
        ecr_uri = _format_ecr_uri(summary['value'])
        name = summary['name']

        result['image_name'] = "{label:>25}:{tag}".format(**ecr_uri)
        result['last_modified'] = summary['last_modified']

        paths[name] = "{last_modified} {image_name}".format(**result)

    click.echo("\n".join(pprint_path_keyval_dict(paths)))


def main():
    cli()
