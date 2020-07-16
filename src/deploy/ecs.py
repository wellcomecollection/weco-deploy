import itertools

from .iam import Iam


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
        service_arns_iterator = self._iterate_all_service()

        services = {}
        for cluster_arn, service_arn in service_arns_iterator:
            if cluster_arn in services:
                services[cluster_arn].append(service_arn)
            else:
                services[cluster_arn] = [service_arn]

        for cluster_arn, service_arns in services.items():
            for service_arns_chunk in Ecs._chunked_iterable(service_arns, 10):
                response = self.ecs.describe_services(
                    cluster=cluster_arn,
                    services=service_arns_chunk,
                    include=[
                        'TAGS',
                    ]
                )

                for service_details in response['services']:
                    self.described_services.append(service_details)

    # Credit to https://alexwlchan.net/2018/12/iterating-in-fixed-size-chunks/
    @staticmethod
    def _chunked_iterable(iterable, size):
        it = iter(iterable)
        while True:
            chunk = tuple(itertools.islice(it, size))
            if not chunk:
                break
            yield chunk

    def _iterate_all_service(self):
        cluster_paginator = self.ecs.get_paginator('list_clusters')
        cluster_iterator = cluster_paginator.paginate()
        service_paginator = self.ecs.get_paginator('list_services')

        for cluster_response in cluster_iterator:
            for cluster_arn in cluster_response['clusterArns']:
                service_iterator = service_paginator.paginate(
                    cluster=cluster_arn
                )

                for service_response in service_iterator:
                    for service_arn in service_response['serviceArns']:
                        yield cluster_arn, service_arn

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
        def _match_deployment_tags(service, desired_service_tag, desired_env_tag):
            tags = service.get('tags')

            if not tags:
                return False

            env_tags = [tag for tag in tags if tag.get('key') == 'deployment:env']
            service_tags = [tag for tag in tags if tag.get('key') == 'deployment:service']

            env_tag = None
            if env_tags:
                env_tag = env_tags[0]['value']

            service_tag = None
            if service_tags:
                service_tag = service_tags[0]['value']

            if env_tag == desired_env_tag and service_tag == desired_service_tag:
                return True
            else:
                return False

        matched_services = [service for service in self.described_services if _match_deployment_tags(
            service, service_id, env
        )]

        if len(matched_services) > 1:
            raise RuntimeError(f"Multiple matching services found for {service_id}/{env}!")

        if len(matched_services) == 0:
            return None
        else:
            return matched_services[0]
