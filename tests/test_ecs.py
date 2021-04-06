import pytest

from deploy.ecs import (
    describe_services,
    find_matching_service,
    list_cluster_arns_in_account,
    list_service_arns_in_cluster
)


@pytest.fixture(scope="session")
def ecs_stack(ecs_client):
    """
    Fixture that creates a basic ECS stack with two clusters and five services.
    """
    ecs_client.create_cluster(clusterName="cluster1")
    ecs_client.create_cluster(clusterName="cluster2")

    ecs_client.create_service(cluster="cluster1", serviceName="service1a")
    ecs_client.create_service(cluster="cluster1", serviceName="service1b")
    ecs_client.create_service(cluster="cluster2", serviceName="service2a")
    ecs_client.create_service(cluster="cluster2", serviceName="service2b")
    ecs_client.create_service(cluster="cluster2", serviceName="service2c")

    return {
        "clusters": ["cluster1", "cluster2"],
        "services": {
            "cluster1": ["service1a", "service1b"],
            "cluster2": ["service2a", "service2b", "service2c"],
        },
    }


def test_list_cluster_arns_in_account(ecs_client, ecs_stack):
    assert list(list_cluster_arns_in_account(ecs_client)) == [
        "arn:aws:ecs:eu-west-1:012345678910:cluster/cluster1",
        "arn:aws:ecs:eu-west-1:012345678910:cluster/cluster2",
    ]


def test_list_service_arns_in_cluster(ecs_client, ecs_stack):
    assert list(list_service_arns_in_cluster(ecs_client, cluster="cluster1")) == [
        "arn:aws:ecs:eu-west-1:012345678910:service/service1a",
        "arn:aws:ecs:eu-west-1:012345678910:service/service1b",
    ]

    assert list(list_service_arns_in_cluster(ecs_client, cluster="cluster2")) == [
        "arn:aws:ecs:eu-west-1:012345678910:service/service2a",
        "arn:aws:ecs:eu-west-1:012345678910:service/service2b",
        "arn:aws:ecs:eu-west-1:012345678910:service/service2c",
    ]


def test_describe_services(ecs_client, ecs_stack):
    service_descriptions = list(describe_services(ecs_client))

    assert len(service_descriptions) == 5
    assert all("tags" in desc for desc in service_descriptions)

    actual_service_names = [desc["serviceName"] for desc in service_descriptions]
    expected_service_names = ecs_stack["services"]["cluster1"] + ecs_stack["services"]["cluster2"]

    assert actual_service_names == expected_service_names


def test_find_matching_service(ecs_client, ecs_stack):
    service_1a = {
        "serviceArn": "serviceArn': 'arn:aws:ecs:eu-west-1:012345678910:service/service1a",
        "tags": [
            {
                "key": "deployment:service",
                "value": "service1",
            },
            {
                "key": "deployment:env",
                "value": "prod",
            },
        ]
    }

    service_1b = {
        "serviceArn": "serviceArn': 'arn:aws:ecs:eu-west-1:012345678910:service/service1b",
        "tags": [
            {
                "key": "deployment:service",
                "value": "service1",
            },
            {
                "key": "deployment:env",
                "value": "staging",
            },
        ]
    }

    service_1c = {
        "serviceArn": "serviceArn': 'arn:aws:ecs:eu-west-1:012345678910:service/service1c",
        "tags": [
            {
                "key": "deployment:service",
                "value": "service1",
            },
            {
                "key": "deployment:env",
                "value": "staging",
            },
        ]
    }

    service_descriptions = [service_1a, service_1b, service_1c]

    assert find_matching_service(
        service_descriptions,
        service_id="service1",
        environment_id="prod"
    ) == service_1a

    assert find_matching_service(
        service_descriptions,
        service_id="service2",
        environment_id="prod"
    ) is None

    with pytest.raises(RuntimeError, match="Multiple matching services found"):
        find_matching_service(
            service_descriptions,
            service_id="service1",
            environment_id="staging"
        )
