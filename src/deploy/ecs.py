from . import iam, tags
from .iterators import chunked_iterable


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


def describe_services(ecs_client):
    """
    Describe all the ECS services in an account.
    """
    for cluster in list_cluster_arns_in_account(ecs_client):
        service_arns = list_service_arns_in_cluster(ecs_client, cluster=cluster)

        # We can specify up to 10 services in a single DescribeServices API call.
        for service_set in chunked_iterable(service_arns, size=10):
            resp = ecs_client.describe_services(
                cluster=cluster,
                services=service_set,
                include=["TAGS"]
            )

            yield from resp["services"]


class Ecs:
    def __init__(self, region_name, role_arn):
        session = iam.get_session(
            session_name="ReleaseToolEcs",
            role_arn=role_arn,
            region_name=region_name
        )
        self.ecs = session.client('ecs')
        self._described_services = list(describe_services(self.ecs))

    def redeploy_service(self, cluster_arn, service_arn, deployment_label):
        response = self.ecs.update_service(
            cluster=cluster_arn,
            service=service_arn,
            forceNewDeployment=True
        )

        self.ecs.tag_resource(
            resourceArn=service_arn,
            tags=[{
                'key': 'deployment:label',
                'value': deployment_label
            }]
        )

        return {
            'cluster_arn': response['service']['clusterArn'],
            'service_arn': response['service']['serviceArn'],
            'deployment_id': response['service']['deployments'][0]['id']
        }

    def find_matching_service(self, *, service_id, environment_id):
        """
        Given a service (e.g. bag-unpacker) and an environment (e.g. prod),
        return the unique matching service.
        """
        try:
            return tags.find_unique_resource_matching_tags(
                self._described_services,
                expected_tags={
                    "deployment:service": service_id,
                    "deployment:env": environment_id,
                }
            )
        except tags.NoMatchingResourceError:
            return None
        except tags.MultipleMatchingResourcesError:
            raise RuntimeError(
                f"Multiple matching services found for {service_id}/{environment_id}!"
            )

    def list_service_tasks(self, service):
        """
        Given a service (e.g. bag-unpacker),
        return a list of tasks running within that service
        """
        service_name = service["response"]["serviceName"]
        cluster_arn = service["response"]["clusterArn"]

        paginator = self.ecs.get_paginator("list_tasks")
        paginator_iter = paginator.paginate(cluster=cluster_arn, serviceName=service_name)
        task_arns = []
        for page in paginator_iter:
            task_arns += page["taskArns"]

        # If task_arns is empty we can't ask to describe them
        if task_arns:
            resp = self.ecs.describe_tasks(
                cluster=cluster_arn,
                tasks=task_arns,
                include=["TAGS"]
            )

            return resp["tasks"]
        else:
            return []
