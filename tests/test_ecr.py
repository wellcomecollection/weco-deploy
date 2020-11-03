import hashlib
import json
from random import random

from botocore.exceptions import ClientError
import moto
import pytest

from deploy import ecr


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


class TestGetRefTagsForImage:
    def test_get_nonexistent_image_is_none(self, ecr_client):
        """
        Looking up an image that doesn't exist, in a repository that does,
        returns None.
        """
        ecr_client.create_repository(repositoryName="empty_repository")

        with pytest.raises(ecr.NoSuchImageError):
            ecr.get_ref_tags_for_image(
                ecr_client,
                repository_name="empty_repository",
                tag="latest",
                account_id="1234567890",
            )

    def test_get_ref_tags_for_image(self, ecr_client, region_name):
        """
        We can store an image in ECR, then retrieve the ref tags on it.
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
        ecr_client.put_image(
            registryId="1234567890",
            repositoryName="example_worker",
            imageManifest=json.dumps(manifest),
            imageTag="ref.456",
        )

        ref_tags = ecr.get_ref_tags_for_image(
            ecr_client,
            repository_name="example_worker",
            tag="latest",
            account_id="1234567890",
        )

        assert ref_tags == {"ref.123", "ref.456"}

    def test_an_unexpected_error_is_raised(self, ecr_client):
        with pytest.raises(ClientError, match="RepositoryNotFoundException"):
            ecr.get_ref_tags_for_image(
                ecr_client,
                repository_name="repo_which_does_not_exist",
                tag="latest",
                account_id="1234567890",
            )

    def test_error_if_image_does_not_have_ref_tag(self, ecr_client, region_name):
        """
        We cannot get the ref URI of an image if there is no ref tag.
        """
        ecr_client.create_repository(repositoryName="example_worker")
        ecr_client.put_image(
            registryId="1234567890",
            repositoryName="example_worker",
            imageManifest=json.dumps(_create_image_manifest()),
            imageTag="latest",
        )

        with pytest.raises(ecr.NoRefTagError):
            ecr.get_ref_tags_for_image(
                ecr_client,
                repository_name="example_worker",
                tag="latest",
                account_id="1234567890",
            )


@moto.mock_sts()
@moto.mock_iam()
def test_get_ref_tags_for_repositories(ecr_client, region_name):
    manifest1 = _create_image_manifest()
    ecr_client.create_repository(repositoryName="example_worker1")
    ecr_client.put_image(
        registryId="1111111111",
        repositoryName="example_worker1",
        imageManifest=json.dumps(manifest1),
        imageTag="latest",
    )
    ecr_client.put_image(
        registryId="1111111111",
        repositoryName="example_worker1",
        imageManifest=json.dumps(manifest1),
        imageTag="ref.111",
    )

    manifest2 = _create_image_manifest()
    ecr_client.create_repository(repositoryName="example_worker2")
    ecr_client.put_image(
        registryId="2222222222",
        repositoryName="example_worker2",
        imageManifest=json.dumps(manifest2),
        imageTag="latest",
    )
    ecr_client.put_image(
        registryId="2222222222",
        repositoryName="example_worker2",
        imageManifest=json.dumps(manifest2),
        imageTag="ref.222",
    )

    ecr_client.create_repository(repositoryName="example_worker3")

    image_repositories = {
        "example_worker1": {
            "account_id": "1111111111",
            "region_name": region_name,
            "role_arn": "arn:aws:iam::1111111111:role/example-role",
            "repository_name": "example_worker1",
        },
        "example_worker2": {
            "account_id": "2222222222",
            "region_name": region_name,
            "role_arn": "arn:aws:iam::2222222222:role/example-role",
            "repository_name": "example_worker2",
        },
        "example_worker3": {
            "account_id": "3333333333",
            "region_name": region_name,
            "role_arn": "arn:aws:iam::3333333333:role/example-role",
            "repository_name": "example_worker3",
        },
    }

    uris = ecr.get_ref_tags_for_repositories(
        image_repositories=image_repositories,
        tag="latest"
    )

    assert uris == {
        "example_worker1": set(["ref.111"]),
        "example_worker2": set(["ref.222"]),
        "example_worker3": set(),
    }
