import os
import secrets

import boto3
import moto
import pytest


@pytest.fixture(scope="session")
def region_name():
    return "eu-west-1"


@pytest.fixture()
def project_id():
    return f"project-{secrets.token_hex()}"


@pytest.fixture()
def role_arn():
    return f"arn:aws:iam::1234567890:role/role-{secrets.token_hex()}"


@pytest.fixture(scope="session")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"


@pytest.fixture(scope="session")
def session(aws_credentials, region_name):
    return boto3.Session(region_name=region_name)


@pytest.fixture(scope="session")
def ecr_client(aws_credentials, region_name):
    with moto.mock_ecr():
        yield boto3.client("ecr", region_name=region_name)


@pytest.fixture(scope="session")
def ecs_client(aws_credentials, region_name):
    with moto.mock_ecs():
        yield boto3.client("ecs", region_name=region_name)
