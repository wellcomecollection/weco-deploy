import hashlib
import json
from random import random
import secrets

from botocore.exceptions import ClientError
import pytest

from deploy import ecr
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


def test_repository_name(ecr_base_uri, repository_name, tag):
    image = EcrImage(
        ecr_base_uri=ecr_base_uri,
        repository_name=repository_name,
        tag=tag,
        describe_images_resp={"imageDetails": [{"repositoryName": repository_name}]},
    )

    assert image.repository_name == repository_name


# Taken from https://github.com/rubelw/mymoto/blob/e43ef43db676058d08855588dd52419a3554e336/moto/tests/test_ecr/test_ecr_boto3.py#L18-L21
def _create_image_digest(contents=None):
    if not contents:
        contents = "docker_image{0}".format(int(random() * 10 ** 6))
    return "sha256:%s" % hashlib.sha256(contents.encode("utf-8")).hexdigest()


# Taken from https://github.com/rubelw/mymoto/blob/e43ef43db676058d08855588dd52419a3554e336/moto/tests/test_ecr/test_ecr_boto3.py#L24-L52
def _create_image_manifest():
    return {
        "schemaVersion": 2,
        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
        "config": {
            "mediaType": "application/vnd.docker.container.image.v1+json",
            "size": 7023,
            "digest": _create_image_digest("config"),
        },
        "layers": [
            {
                "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
                "size": 32654,
                "digest": _create_image_digest("layer1"),
            },
            {
                "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
                "size": 16724,
                "digest": _create_image_digest("layer2"),
            },
            {
                "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
                "size": 73109,
                # randomize image digest
                "digest": _create_image_digest(),
            },
        ],
    }


class TestGetRefUriForImage:
    def test_get_nonexistent_image_is_none(self, ecr_client):
        """
        Looking up an image that doesn't exist, in a repository that does,
        returns None.
        """
        ecr_client.create_repository(repositoryName="empty_repository")

        with pytest.raises(ecr.NoSuchImageError):
            ecr.get_ref_uri_for_image(
                ecr_client,
                ecr_base_uri="1234567890.ecr.example.aws.com",
                repository_name="empty_repository",
                tag="latest",
                account_id="1234567890",
            )

    def test_get_ref_uri_for_image(self, ecr_client, region_name):
        """
        We can store an image in ECR, then retrieve it with get_ref_uri_for_image.
        """
        manifest = _create_image_manifest()

        ecr_client.create_repository(repositoryName="example_worker")
        ecr_client.put_image(
            registryId="1234567890",
            repositoryName="example_worker",
            imageManifest=json.dumps(manifest),
            imageTag="latest",
        )
        ecr_client.put_image(
            registryId="1234567890",
            repositoryName="example_worker",
            imageManifest=json.dumps(manifest),
            imageTag="ref.123",
        )

        ref_uri = ecr.get_ref_uri_for_image(
            ecr_client,
            ecr_base_uri="1234567890.ecr.example.aws.com",
            repository_name="example_worker",
            tag="latest",
            account_id="1234567890",
        )

        assert ref_uri == "1234567890.ecr.example.aws.com/example_worker:ref.123"

    def test_an_unexpected_error_is_raised(self, ecr_client):
        with pytest.raises(ClientError, match="RepositoryNotFoundException"):
            ecr.get_ref_uri_for_image(
                ecr_client,
                ecr_base_uri="1234567890.ecr.example.aws.com",
                repository_name="repo_which_does_not_exist",
                tag="latest",
                account_id="1234567890",
            )
