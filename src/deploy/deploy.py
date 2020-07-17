import click
import json

from dateutil.parser import parse
from urllib.parse import urlparse
from pprint import pprint

from .ecr import Ecr
from .ecs import Ecs
from .model import create_deployment, create_release
from .config import load, get_environments_lookup

from .releases_store import DynamoDbReleaseStore
from .parameter_store import SsmParameterStore
from .pretty_printing import pprint_path_keyval_dict
from .iam import Iam

from.project import Projects

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
        'project': config,
        'project2': project
    }


@cli.command()
@click.option("--service-id", required=True)
@click.option("--namespace", required=True, default=DEFAULT_ECR_NAMESPACE)
@click.option("--label", default="latest")
@click.pass_context
def publish(ctx, service_id, namespace, label):
    project = ctx.obj['project']
    dry_run = ctx.obj['dry_run']

    role_arn = project['role_arn']
    account_id = project['account_id']
    region_name = project['aws_region_name']

    ecr = Ecr(account_id, region_name, role_arn)
    parameter_store = SsmParameterStore(project['id'], region_name, role_arn)

    click.echo(click.style(f"Attempting to publish {project['id']}/{service_id}", fg="blue"))
    click.echo(click.style(f"Authenticating {account_id} for `docker push` with ECR", fg="yellow"))

    ecr.login()

    remote_image_name, remote_image_tag, local_image_tag = ecr.publish_image(
        namespace,
        service_id,
        dry_run
    )

    click.echo(click.style(f"Published Image {local_image_tag} to {remote_image_name}", fg="yellow"))

    ecr.tag_image(
        namespace,
        service_id,
        remote_image_tag,
        label
    )

    click.echo(click.style(f"Tagged {remote_image_name} to {remote_image_name}", fg="yellow"))

    ssm_path = parameter_store.update_ssm(
        service_id,
        label,
        remote_image_name,
        dry_run
    )

    click.echo(click.style(f"Updated SSM path {ssm_path} to {remote_image_name}", fg="yellow"))

    click.echo(click.style(f"Done publishing {project['id']}/{service_id}", fg="green"))


def _deploy(project, dry_run, confirm, release_id, environment_id, namespace, description):
    project_id = project["id"]
    account_id = project['account_id']
    role_arn = project['role_arn']
    region_name = project['aws_region_name']

    releases_store = DynamoDbReleaseStore(
        project_id=project["id"],
        region_name=region_name,
        role_arn=role_arn
    )

    parameter_store = SsmParameterStore(
        project_id=project_id,
        region_name=region_name,
        role_arn=role_arn
    )

    ecr = Ecr(
        account_id=account_id,
        region_name=region_name,
        role_arn=role_arn
    )

    ecs = Ecs(
        account_id=account_id,
        region_name=region_name,
        role_arn=role_arn
    )

    user_details = Iam(
        role_arn=role_arn,
        region_name=region_name
    )

    environments = get_environments_lookup(project)

    try:
        environment = environments[environment_id]
    except KeyError:
        raise ValueError(f"Unknown environment. Expected '{environment_id}' in {environments}")

    if release_id == "latest":
        release = releases_store.get_latest_release()
    else:
        release = releases_store.get_release(release_id)

    click.echo("")
    click.echo(click.style(f"Deploying release {release['release_id']}", fg="blue"))
    click.echo(click.style(f"Requested by: {release['requested_by']}", fg="yellow"))
    click.echo(click.style(f"Date created: {release['date_created']}", fg="yellow"))

    click.echo("")
    matched_services = {}
    for image_id, image_uri in release['images'].items():
        click.echo(click.style(f"{image_id}: {image_uri}", fg="bright_yellow"))

        image_repositories = project.get('image_repositories')

        # Naively assume service name matches image id
        service_ids = [image_id]

        # Attempt to match deployment image id to config and override service_ids
        if image_repositories:
            matched_image_ids = [image for image in image_repositories if image['id'] == image_id]

            if matched_image_ids:
                matched_image_id = matched_image_ids[0]
                service_ids = matched_image_id.get('services')

        # Attempt to match service ids to ECS services
        available_services = [ecs.get_service(service_id, environment_id) for service_id in service_ids]
        available_services = [service for service in available_services if service]

        if available_services:
            matched_services[image_id] = available_services
            service_arns = [service['serviceArn'] for service in available_services]
            click.echo(click.style(f"{image_id}: ECS Services discovered: {service_arns}", fg="bright_yellow"))

    if not confirm:
        click.echo("")
        click.confirm(click.style("Create deployment?", fg="green", bold=True), abort=True)

    caller_identity = user_details.caller_identity(underlying=True)
    deployment = create_deployment(environment, caller_identity['arn'], description)

    click.echo("")
    click.echo(click.style("Created deployment.", fg="green"))
    click.echo("")
    click.echo(click.style(f"Requested by: {deployment['requested_by']}", fg="yellow"))
    click.echo(click.style(f"Date created: {deployment['date_created']}", fg="yellow"))

    click.echo("")
    for image_id, image_name in release['images'].items():
        ssm_path = parameter_store.update_ssm(
            service_id=image_id,
            label=environment_id,
            image_name=image_name,
            dry_run=dry_run
        )

        click.echo(click.style(f"{image_id}: Updated SSM path {ssm_path} to {image_name}", fg="bright_yellow"))

        old_tag = image_name.split(":")[-1]
        new_tag = f"env.{environment_id}"

        result = ecr.tag_image(
            namespace=namespace,
            service_id=image_id,
            tag=old_tag,
            new_tag=new_tag,
            dry_run=dry_run
        )

        if result['status'] == 'success':
            click.echo(click.style(
                f"{image_id}: Re-tagged image {image_id}:{old_tag} to {image_id}:{new_tag}",
                fg="bright_yellow"
            ))
        else:
            click.echo(click.style(
                f"{image_id}: Already tagged image {image_id}:{old_tag} to {image_id}:{new_tag} (nothing to do)",
                fg="yellow"
            ))

        if image_id in matched_services:
            deployments = [ecs.redeploy_service(
                service['clusterArn'],
                service['serviceArn']
            ) for service in matched_services.get(image_id)]

            for deployment in deployments:
                service_arn = deployment['service_arn']
                deployment_id = deployment['deployment_id']
                click.echo(click.style(
                    f"{image_id}: ECS Service deployed {service_arn} to {deployment_id}",
                    fg="bright_yellow"
                ))

    if dry_run:
        click.echo("dry-run, not created.")

    click.echo("")
    click.echo(click.style(f"Deployed {image_id} to {new_tag}", fg="green"))


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

    project2 = ctx.obj['project2']

    release = project2.get_release(release_id)
    environment = project2.get_environment(environment_id)

    click.echo("")
    click.echo(click.style(f"Deploying release:  {release['release_id']}", fg="blue"))
    click.echo(click.style(f"Targeting env: {environment['id']}, ({environment['name']})", fg="yellow"))
    click.echo(click.style(f"Requested by: {release['requested_by']}", fg="yellow"))
    click.echo(click.style(f"Date created: {release['date_created']}", fg="yellow"))

    ecs_services = project2.get_ecs_services(release_id, environment_id)

    for image_id, services in ecs_services.items():
        service_arns = [service['serviceArn'] for service in services]
        click.echo(click.style(f"{image_id}: ECS Services discovered: {service_arns}", fg="bright_yellow"))

    if not confirm:
        click.echo("")
        click.confirm(click.style("Create deployment?", fg="cyan", bold=True), abort=True)

    result = project2.deploy(release_id, environment_id, namespace, description)

    click.echo("")
    click.echo(click.style(f"Deployment Summary", fg="bright_green"))
    click.echo(click.style(f"Requested by: {result['requested_by']}", fg="green"))
    click.echo(click.style(f"Date created: {result['date_created']}", fg="green"))
    click.echo("")
    for image_id, summary in result['details'].items():
        click.echo(click.style(
            f"{image_id}: SSM Updated {summary['ssm_result']['ssm_path']} to {summary['ssm_result']['image_name']}",
            fg="green"
        ))
        click.echo(click.style(
            f"{image_id}: ECR Updated {summary['tag_result']['source']} to {summary['tag_result']['target']}",
            fg="green"
        ))

        for ecs_deployment in summary['ecs_deployments']:
            click.echo(click.style(
                f"{image_id}: ECS Deployed {ecs_deployment['service_arn']} to {ecs_deployment['deployment_id']}",
                fg="green"
            ))

    click.echo("")


def _prepare(project, dry_run, from_label, service_id, description):
    project_id = project['id']
    project_name = project['name']
    account_id = project['account_id']
    region_name = project['aws_region_name']
    role_arn = project['role_arn']

    releases_store = DynamoDbReleaseStore(
        project_id=project_id,
        region_name=region_name,
        role_arn=role_arn
    )

    parameter_store = SsmParameterStore(
        project_id=project_id,
        region_name=region_name,
        role_arn=role_arn
    )

    ecr = Ecr(
        account_id=account_id,
        region_name=region_name,
        role_arn=role_arn
    )

    user_details = Iam(
        role_arn=role_arn,
        region_name=region_name
    )

    image_repositories = project.get('image_repositories')

    from_images = {}
    if image_repositories:
        for image in image_repositories:
            image_id = image['id']
            account_id = image.get('account_id', account_id)
            namespace = image.get('namespace', DEFAULT_ECR_NAMESPACE)

            image_details = ecr.describe_image(namespace, image_id, from_label, account_id)
            from_images[image_details['service_id']] = image_details['ref']
    else:
        from_images = parameter_store.get_services_to_images(from_label)

    service_source = "latest"
    if service_id == "all":
        release_image = {}
    else:
        service_source = click.prompt("Label or image URI to release for specified service", default="latest")
        if _is_url(service_source):
            release_image = {service_id: service_source}
        else:
            if image_repositories:
                image_details = ecr.describe_image(namespace, service_id, service_source, account_id)
                release_image = {image_details['service_id']: image_details['ref']}
            else:
                release_image = parameter_store.get_service_to_image(service_source, service_id)

    release_images = {**from_images, **release_image}

    if not release_images:
        raise click.UsageError(f"No images found for {project['id']} {service_id} {from_label}")

    caller_identity = user_details.caller_identity(underlying=True)

    release = create_release(
        project_id=project_id,
        project_name=project_name,
        current_user=caller_identity['arn'],
        description=description,
        images=release_images
    )

    click.echo("")
    if service_id == "all":
        click.echo(click.style(
            f"Prepared release from images in {from_label}", fg="blue")
        )
    else:
        click.echo(click.style(
            f"Prepared release from images in {from_label} with {service_id} from {service_source}", fg="blue")
        )

    click.echo(click.style(f"Requested by: {release['requested_by']}", fg="yellow"))
    click.echo(click.style(f"Date created: {release['date_created']}", fg="yellow"))
    click.echo("")

    for service, image in release['images'].items():
        click.echo(click.style(f"{service}: {image}", fg="bright_yellow"))

    click.echo("")

    click.echo(click.style(f"Created release {release['release_id']}", fg="green"))

    if not dry_run:
        releases_store.put_release(release)
    else:
        click.echo("dry-run, not created.")

    return release['release_id']


@cli.command()
@click.option('--from-label', prompt="Label to base release upon",
              help="The existing label upon which this release will be based", default="latest", show_default=True)
@click.option('--service-id', prompt="Service to update", default="all", show_default=True,
              help="The service to update with a (prompted for) new image")
@click.option('--release-description', prompt="Description for this release", default="No description provided")
@click.pass_context
def prepare(ctx, from_label, service_id, release_description):
    project = ctx.obj['project']
    dry_run = ctx.obj['dry_run']

    _prepare(project, dry_run, from_label, service_id, release_description)


@cli.command()
@click.option('--from-label', prompt="Label to base release upon",
              help="The existing label upon which this release will be based", default="latest", show_default=True)
@click.option('--service-id', prompt="Service to update", default="all", show_default=True,
              help="The service to update with a (prompted for) new image")
@click.option('--environment-id', prompt="Environment ID to deploy release to",
              default="stage", show_default=True,
              help="The target environment of this deployment")
@click.option("--namespace", default=DEFAULT_ECR_NAMESPACE, show_default=True)
@click.option('--description', prompt="Enter a description for this deployment",
              help="A description of this deployment", default="No description provided")
@click.pass_context
def release_deploy(ctx, from_label, service_id, environment_id, namespace, description):
    project = ctx.obj['project']
    role_arn = ctx.obj['role_arn']
    dry_run = ctx.obj['dry_run']
    confirm = ctx.obj['confirm']

    release_id = _prepare(project, role_arn, dry_run, from_label, service_id, description)
    _deploy(project, role_arn, dry_run, confirm, release_id, environment_id, namespace, description)


@cli.command()
@click.argument('release_id', required=False)
@click.pass_context
def show_release(ctx, release_id):
    project = ctx.obj['project']
    role_arn = ctx.obj['role_arn']
    region_name = project['aws_region_name']

    releases_store = DynamoDbReleaseStore(
        project_id=project["id"],
        region_name=region_name,
        role_arn=role_arn
    )

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
    region_name = project['aws_region_name']

    releases_store = DynamoDbReleaseStore(
        project_id=project["id"],
        region_name=region_name,
        role_arn=role_arn
    )

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
    region_name = project['aws_region_name']

    parameter_store = SsmParameterStore(
        project_id=project['id'],
        region_name=region_name,
        role_arn=role_arn
    )

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
