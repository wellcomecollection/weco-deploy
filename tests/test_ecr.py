import secrets

import pytest

from deploy.ecr import EcrImage
from deploy.exceptions import EcrError


@pytest.fixture
def repository_name():
    return f"repo-{secrets.token_hex()}"


@pytest.fixture
def tag():
    return f"tag-{secrets.token_hex()}"


@pytest.fixture
def ecr_base_uri():
    return "1234567890.ecr.example.aws.com"


def test_no_image_details_is_error(ecr_base_uri, repository_name, tag):
    """
    If the response from the ECR DescribeImage API doesn't contain an "imageDetails"
    field, we throw an error.
    """
    with pytest.raises(
        EcrError, match=f"No matching images found for {repository_name}:{tag}!"
    ):
        EcrImage(
            ecr_base_uri=ecr_base_uri,
            repository_name=repository_name,
            tag=tag,
            describe_images_resp={"imageDetails": []},
        )


def test_multiple_matching_images_is_error(ecr_base_uri, repository_name, tag):
    """
    If the response from the ECR DescribeImage API contains multiple images in
    the "imageDetails" field, we throw an error.
    """
    repository_name = "example"
    tag = "123"

    with pytest.raises(
        EcrError, match=f"Multiple matching images found for {repository_name}:{tag}!"
    ):
        EcrImage(
            ecr_base_uri=ecr_base_uri,
            repository_name=repository_name,
            tag=tag,
            describe_images_resp={
                "imageDetails": [{"name": "image1"}, {"name": "image2"}]
            },
        )


@pytest.mark.parametrize(
    "imageTags, is_latest", [(["latest", "env.stage"], True), (["env.prod"], False),]
)
def test_latest(repository_name, tag, imageTags, is_latest):
    image = EcrImage(
        ecr_base_uri=ecr_base_uri,
        repository_name=repository_name,
        tag=tag,
        describe_images_resp={
            "imageDetails": [{"name": "my_image", "imageTags": imageTags}]
        },
    )

    assert image.is_latest == is_latest


def test_no_ref_tag_is_error(ecr_base_uri, repository_name, tag):
    image = EcrImage(
        ecr_base_uri=ecr_base_uri,
        repository_name=repository_name,
        tag=tag,
        describe_images_resp={"imageDetails": [{"name": "my_image", "imageTags": []}]},
    )

    with pytest.raises(
        EcrError, match=f"No matching ref tags found for {repository_name}:{tag}!"
    ):
        image.ref_uri()


def test_gets_ref_uri():
    image = EcrImage(
        ecr_base_uri="1234567890.ecr.example.aws.com",
        repository_name="example_worker",
        tag="123abc",
        describe_images_resp={
            "imageDetails": [{"name": "my_image", "imageTags": ["ref.abcdef1"]}]
        },
    )

    assert (
        image.ref_uri() == "1234567890.ecr.example.aws.com/example_worker:ref.abcdef1"
    )


def test_chooses_ref_uri_arbitrarily():
    image = EcrImage(
        ecr_base_uri="1234567890.ecr.example.aws.com",
        repository_name="example_worker",
        tag="123abc",
        describe_images_resp={
            "imageDetails": [
                {"name": "my_image", "imageTags": ["ref.abcdef1", "ref.1fedcba"]}
            ]
        },
    )

    assert image.ref_uri() in {
        "1234567890.ecr.example.aws.com/example_worker:ref.abcdef1",
        "1234567890.ecr.example.aws.com/example_worker:ref.1fedcba",
    }


def test_registry_id(ecr_base_uri, repository_name, tag):
    image = EcrImage(
        ecr_base_uri=ecr_base_uri,
        repository_name=repository_name,
        tag=tag,
        describe_images_resp={"imageDetails": [{"registryId": "1234567890"}]},
    )

    assert image.registry_id == "1234567890"


def test_repository_name(ecr_base_uri, repository_name, tag):
    image = EcrImage(
        ecr_base_uri=ecr_base_uri,
        repository_name=repository_name,
        tag=tag,
        describe_images_resp={"imageDetails": [{"repositoryName": repository_name}]},
    )

    assert image.repository_name == repository_name


def test_image_digest(ecr_base_uri, repository_name, tag):
    image = EcrImage(
        ecr_base_uri=ecr_base_uri,
        repository_name=repository_name,
        tag=tag,
        describe_images_resp={"imageDetails": [{"imageDigest": "sha256:123456789abc"}]},
    )

    assert image.image_digest == "sha256:123456789abc"
