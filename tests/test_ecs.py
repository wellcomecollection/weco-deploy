import pytest

from deploy.ecs import (
    deploy_service,
    describe_services,
    find_ecs_services_for_release,
    find_matching_service,
    find_service_arns_for_release,
    list_cluster_arns_in_account,
    list_service_arns_in_cluster,
    list_tasks_in_service,
    MultipleMatchingServicesError,
    NoMatchingServiceError,
)
from deploy.models import ImageRepository, Project, Service
from deploy.tags import parse_aws_tags


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


def test_describe_services(session, ecs_stack):
    service_descriptions = describe_services(session)

    assert len(service_descriptions) == 5
    assert all("tags" in desc for desc in service_descriptions)

    actual_service_names = [desc["serviceName"] for desc in service_descriptions]
    expected_service_names = ecs_stack["services"]["cluster1"] + ecs_stack["services"]["cluster2"]

    assert actual_service_names == expected_service_names


def test_find_matching_service(ecs_client, ecs_stack):
    service_1a = {
        "serviceArn": "arn:aws:ecs:eu-west-1:012345678910:service/service1a",
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
        "serviceArn": "arn:aws:ecs:eu-west-1:012345678910:service/service1b",
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
        "serviceArn": "arn:aws:ecs:eu-west-1:012345678910:service/service1c",
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

    with pytest.raises(NoMatchingServiceError):
        assert find_matching_service(
            service_descriptions,
            service_id="service2",
            environment_id="prod"
        )

    with pytest.raises(MultipleMatchingServicesError):
        find_matching_service(
            service_descriptions,
            service_id="service1",
            environment_id="staging"
        )


def test_find_service_arns_for_release(ecs_client, ecs_stack):
    service_1a = {
        "serviceArn": "arn:aws:ecs:eu-west-1:012345678910:service/service1a",
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
        "serviceArn": "arn:aws:ecs:eu-west-1:012345678910:service/service1b",
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
        "serviceArn": "arn:aws:ecs:eu-west-1:012345678910:service/service2",
        "tags": [
            {
                "key": "deployment:service",
                "value": "service2",
            },
            {
                "key": "deployment:env",
                "value": "prod",
            },
        ]
    }

    service_descriptions = [service_1a, service_1b, service_1c]

    project = Project(
        name="Example Project",
        role_arn="arn:aws:iam::123456789012:role/example-ci",
        image_repositories=[
            ImageRepository(id="repo1", services=[Service(id="service1")]),
            ImageRepository(id="repo2", services=[Service(id="service2")])
        ]
    )

    result = find_service_arns_for_release(
        project=project,
        release={"images": ["repo1", "repo2", "repo3"]},
        service_descriptions=service_descriptions,
        environment_id="prod"
    )

    assert result == {
        "repo1": ["arn:aws:ecs:eu-west-1:012345678910:service/service1a"],
        "repo2": ["arn:aws:ecs:eu-west-1:012345678910:service/service2"],
        "repo3": []
    }

    result = find_service_arns_for_release(
        project=project,
        release={"images": ["repo1", "repo2"]},
        service_descriptions=service_descriptions,
        environment_id="staging"
    )

    assert result == {
        "repo1": ["arn:aws:ecs:eu-west-1:012345678910:service/service1b"],
        "repo2": [],
    }


def test_list_tasks_in_service(session, ecs_stack):
    # Annoyingly, there's no way for the StartTask API to start tasks in
    # a named service, so we'll never find anything useful here.
    #
    # I'm calling the method so we get some sense checking that it's
    # not completely broken, but it'd be nice if we could test it
    # more thoroughly.

    resp = list_tasks_in_service(
        session,
        cluster="arn:aws:ecs:eu-west-1:012345678910:cluster/cluster1",
        service_name="service1a"
    )
    assert resp == []


def test_find_ecs_services_for_release(session, ecs_stack):
    project = Project(
        name="Example Project",
        role_arn="arn:aws:iam::123456789012:role/example-ci",
        image_repositories=[
            ImageRepository(id="repo1", services=[Service(id="service1")]),
            ImageRepository(id="repo2", services=[Service(id="service2")])
        ]
    )

    service_1_prod = {
        "serviceArn": "arn:aws:ecs:eu-west-1:012345678910:service/service1a",
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

    service_1_staging = {
        "serviceArn": "arn:aws:ecs:eu-west-1:012345678910:service/service1b",
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

    service_2_prod = {
        "serviceArn": "arn:aws:ecs:eu-west-1:012345678910:service/service2",
        "tags": [
            {
                "key": "deployment:service",
                "value": "service2",
            },
            {
                "key": "deployment:env",
                "value": "prod",
            },
        ]
    }

    service_descriptions = [service_1_prod, service_1_staging, service_2_prod]

    resp = find_ecs_services_for_release(
        project=project,
        service_descriptions=service_descriptions,
        release={
            "images": {
                "repo1": "edu.self/service1:ref.123456",
                "repo2": "edu.self/service2:ref.123456",
                "repo3": "edu.self/service3:ref.123456",
            }
        },
        environment_id="prod"
    )

    assert resp == {
        "repo1": {"service1": service_1_prod},
        "repo2": {"service2": service_2_prod},
    }
