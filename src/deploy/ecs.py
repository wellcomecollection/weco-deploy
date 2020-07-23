from .iam import Iam
from .iterators import chunked_iterable
from .tags import parse_aws_tags


class Ecs:
    def __init__(self, account_id, region_name, role_arn):
        self.account_id = account_id
        self.region_name = region_name
        self.session = Iam.get_session(
            session_name="ReleaseToolEcs",
            role_arn=role_arn,
            region_name=region_name
        )
        self.ecs = self.session.client('ecs')
        self.described_services = []
        self._load_described_services()

    def _load_described_services(self):
        for cluster_arn in self.list_cluster_arns():
            service_arns = self.list_service_arns(cluster_arn=cluster_arn)

            # We can specify up to 10 services in a single DescribeServices API call.
            for service_set in chunked_iterable(service_arns, size=10):
                resp = self.ecs.describe_services(
                    cluster=cluster_arn,
                    services=service_set,
                    include=["TAGS"]
                )

                for service_description in resp["services"]:
                    self.described_services.append(service_description)

    def list_cluster_arns(self):
        """
        Generates the ARN of every ECS cluster in an account.
        """
        paginator = self.ecs.get_paginator("list_clusters")

        for page in paginator.paginate():
            yield from page["clusterArns"]

    def list_service_arns(self, *, cluster_arn):
        """
        Generates the ARN of every ECS service in a cluster.
        """
        paginator = self.ecs.get_paginator("list_services")

        for page in paginator.paginate(cluster=cluster_arn):
            yield from page["serviceArns"]

    def redeploy_service(self, cluster_arn, service_arn):
        response = self.ecs.update_service(
            cluster=cluster_arn,
            service=service_arn,
            forceNewDeployment=True
        )

        return {
            'cluster_arn': response['service']['clusterArn'],
            'service_arn': response['service']['serviceArn'],
            'deployment_id': response['service']['deployments'][0]['id']
        }

    def get_service(self, service_id, env):
        """
        Given a service ID (e.g. bag-unpacker) and an environment (e.g. prod),
        return the unique matching service.
        """
        def _has_matching_tags(service):
            service_tags = parse_aws_tags(service.get("tags", []))

            return (
                service_tags.get("deployment:service") == service_id and
                service_tags.get("deployment:env") == env
            )

        matched_services = [
            service
            for service in self.described_services
            if _has_matching_tags(service)
        ]

        if len(matched_services) > 1:
            raise RuntimeError(f"Multiple matching services found for {service_id}/{env}: ({matched_services}!")

        if len(matched_services) == 0:
            return None
        else:
            return matched_services[0]
