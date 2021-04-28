import collections
import typing

from . import tags
from .iterators import chunked_iterable
from .models import Project


def list_cluster_arns_in_account(ecs_client):
    """
    Generates the ARN of every ECS cluster in an account.
    """
    paginator = ecs_client.get_paginator("list_clusters")

    for page in paginator.paginate():
        yield from page["clusterArns"]


def list_service_arns_in_cluster(ecs_client, *, cluster):
    """
    Generates the ARN of every ECS service in a cluster.
    """
    paginator = ecs_client.get_paginator("list_services")

    for page in paginator.paginate(cluster=cluster):
        yield from page["serviceArns"]


def describe_services(session):
    """
    Describe all the ECS services in an account.
    """
    ecs_client = session.client("ecs")
    result = []

    for cluster in list_cluster_arns_in_account(ecs_client):
        service_arns = list_service_arns_in_cluster(ecs_client, cluster=cluster)

        # We can specify up to 10 services in a single DescribeServices API call.
        for service_set in chunked_iterable(service_arns, size=10):
            resp = ecs_client.describe_services(
                cluster=cluster,
                services=service_set,
                include=["TAGS"]
            )

            result.extend(resp["services"])

    return result


class NoMatchingServiceError(Exception):
    pass


class MultipleMatchingServicesError(Exception):
    pass


def find_matching_service(
    service_descriptions, *, service_id, environment_id
):
    """
    Given a service (e.g. bag-unpacker) and an environment (e.g. prod),
    return the unique matching service.
    """
    try:
        return tags.find_unique_resource_matching_tags(
            service_descriptions,
            expected_tags={
                "deployment:service": service_id,
                "deployment:env": environment_id,
            }
        )
    except tags.NoMatchingResourceError:
        raise NoMatchingServiceError(
            f"No matching service found for {service_id}/{environment_id}!"
        )
    except tags.MultipleMatchingResourcesError:
        raise MultipleMatchingServicesError(
            f"Multiple matching services found for {service_id}/{environment_id}!"
        )


def find_service_arns_for_release(
    *, project: Project, release, service_descriptions, environment_id
):
    """
    Build a dictionary (image ID) -> list(service ARNs) for all the images
    in a particular release.
    """
    result = {image_id: [] for image_id in release["images"]}

    for image_id in release["images"]:
        try:
            services = project.image_repositories[image_id].services
        except KeyError:
            continue

        for service_id in services:
            try:
                matching_service = find_matching_service(
                    service_descriptions,
                    service_id=service_id,
                    environment_id=environment_id
                )
            except NoMatchingServiceError:
                continue

            result[image_id].append(matching_service["serviceArn"])

    return result


def deploy_service(session, *, cluster_arn, service_arn, deployment_label):
    """
    Triggers a deployment of a given service.
    """
    ecs_client = session.client("ecs")

    resp = ecs_client.update_service(
        cluster=cluster_arn,
        service=service_arn,
        forceNewDeployment=True
    )

    ecs_client.tag_resource(
        resourceArn=service_arn,
        tags=tags.to_aws_tags({"deployment:label": deployment_label})
    )

    return {
        "cluster_arn": resp["service"]["clusterArn"],
        "service_arn": resp["service"]["serviceArn"],
        "deployment_id": resp["service"]["deployments"][0]["id"]
    }


def list_tasks_in_service(session, *, cluster_arn, service_name):
    """
    Given the name of a service, return a list of tasks running within
    the service.
    """
    ecs_client = session.client("ecs")

    task_arns = []

    paginator = ecs_client.get_paginator("list_tasks")
    for page in paginator.paginate(
        cluster=cluster_arn, serviceName=service_name
    ):
        task_arns.extend(page["taskArns"])

    # If task_arns is empty we can't ask to describe them.
    # TODO: This method can handle up to 100 task ARNs.  It seems unlikely
    # we'd ever have more than that, hence not handling it properly.
    if task_arns:
        resp = ecs_client.describe_tasks(
            cluster=cluster_arn,
            tasks=task_arns,
            include=["TAGS"]
        )

        return resp["tasks"]
    else:
        return []


def find_ecs_services_for_release(
    *,
    project: Project,
    service_descriptions: typing.List[typing.Dict],
    release: str,
    environment_id: str
):
    """
    Returns a map (image ID) -> Dict(service ID -> ECS service description)
    """
    matched_services = collections.defaultdict(dict)

    for image_id, _ in release['images'].items():
        # Attempt to match deployment image id to config and override service_ids
        try:
            matched_image = project.image_repositories[image_id]
        except KeyError:
            continue

        for service_id in matched_image.services:
            try:
                service_description = find_matching_service(
                    service_descriptions=service_descriptions,
                    service_id=service_id,
                    environment_id=environment_id
                )

                matched_services[image_id] = {
                    service_id: service_description
                }
            except NoMatchingServiceError:
                pass

    return matched_services
