import json
import secrets

from botocore.exceptions import ClientError
import moto
import pytest

from deploy import ecr
from utils import create_image_manifest


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
                tag="latest"
            )

    def test_get_ref_tags_for_image(self, ecr_client, region_name):
        """
        We can store an image in ECR, then retrieve the ref tags on it.
        """
        manifest = create_image_manifest()

        ecr_client.create_repository(repositoryName="example_worker")
        ecr_client.put_image(
            repositoryName="example_worker",
            imageManifest=json.dumps(manifest),
            imageTag="latest",
        )
        ecr_client.put_image(
            repositoryName="example_worker",
            imageManifest=json.dumps(manifest),
            imageTag="ref.123",
        )
        ecr_client.put_image(
            repositoryName="example_worker",
            imageManifest=json.dumps(manifest),
            imageTag="ref.456",
        )

        ref_tags = ecr.get_ref_tags_for_image(
            ecr_client,
            repository_name="example_worker",
            tag="latest"
        )

        assert ref_tags == {"ref.123", "ref.456"}

    def test_an_unexpected_error_is_raised(self, ecr_client):
        with pytest.raises(ClientError, match="RepositoryNotFoundException"):
            ecr.get_ref_tags_for_image(
                ecr_client,
                repository_name="repo_which_does_not_exist",
                tag="latest"
            )

    def test_error_if_image_does_not_have_ref_tag(self, ecr_client, region_name):
        """
        We cannot get the ref URI of an image if there is no ref tag.
        """
        ecr_client.create_repository(repositoryName="example_worker")
        ecr_client.put_image(
            repositoryName="example_worker",
            imageManifest=json.dumps(create_image_manifest()),
            imageTag="latest",
        )

        with pytest.raises(ecr.NoRefTagError):
            ecr.get_ref_tags_for_image(
                ecr_client, repository_name="example_worker", tag="latest"
            )


@moto.mock_sts()
def test_get_public_image_uri(role_arn):
    ecr_public = ecr.EcrPublic(gallery_id="abcdef", role_arn=role_arn)

    assert (
        ecr_public.get_image_uri(image_id="example_worker", tag="latest") ==
        "public.ecr.aws/abcdef/uk.ac.wellcome/example_worker:latest"
    )


@moto.mock_sts()
def test_get_private_image_uri(region_name, role_arn):
    ecr_private = ecr.EcrPrivate(
        region_name=region_name,
        role_arn=f"arn:aws:iam::1234567890:role/role-{secrets.token_hex()}"
    )

    assert (
        ecr_private.get_image_uri(image_id="example_worker", tag="latest") ==
        f"1234567890.dkr.ecr.{region_name}.amazonaws.com/uk.ac.wellcome/example_worker:latest"
    )


@moto.mock_sts()
@moto.mock_iam()
def test_get_ref_tags_for_repositories(ecr_client, role_arn, region_name):
    manifest1 = create_image_manifest()
    ecr_client.create_repository(
        repositoryName="uk.ac.wellcome/example_worker1"
    )
    ecr_client.put_image(
        repositoryName="uk.ac.wellcome/example_worker1",
        imageManifest=json.dumps(manifest1),
        imageTag="latest",
    )
    ecr_client.put_image(
        repositoryName="uk.ac.wellcome/example_worker1",
        imageManifest=json.dumps(manifest1),
        imageTag="ref.111",
    )

    manifest2 = create_image_manifest()
    ecr_client.create_repository(
        repositoryName="uk.ac.wellcome/example_worker2"
    )
    ecr_client.put_image(
        repositoryName="uk.ac.wellcome/example_worker2",
        imageManifest=json.dumps(manifest2),
        imageTag="latest",
    )
    ecr_client.put_image(
        repositoryName="uk.ac.wellcome/example_worker2",
        imageManifest=json.dumps(manifest2),
        imageTag="ref.222",
    )

    ecr_client.create_repository(
        repositoryName="uk.ac.wellcome/example_worker3"
    )

    image_repositories = {
        "example_worker1": {
            "region_name": region_name,
            "role_arn": "arn:aws:iam::1111111111:role/example-role",
        },
        "example_worker2": {
            "region_name": region_name,
            "role_arn": "arn:aws:iam::2222222222:role/example-role",
        },
        "example_worker3": {
            "region_name": region_name,
            "role_arn": "arn:aws:iam::3333333333:role/example-role",
        },
    }

    ecr_private = ecr.EcrPrivate(role_arn=role_arn, region_name=region_name)

    uris = ecr_private.get_ref_tags_for_repositories(
        image_repositories=image_repositories,
        tag="latest"
    )

    assert uris == {
        "example_worker1": set(["ref.111"]),
        "example_worker2": set(["ref.222"]),
        "example_worker3": set(),
    }


@pytest.mark.parametrize(
    "image_uri, expected_result",
    [
        (
            "760097843905.dkr.ecr.eu-west-1.amazonaws.com/uk.ac.wellcome/nginx_apigw:f1188c2a7df01663dd96c99b26666085a4192167",
            {
                "registry_id": "760097843905",
                "repository_name": "uk.ac.wellcome/nginx_apigw",
                "image_tag": "f1188c2a7df01663dd96c99b26666085a4192167",
            },
        ),
        (
            "760097843905.dkr.ecr.eu-west-1.amazonaws.com/uk.ac.wellcome/id_minter:env.2022-08-24",
            {
                "registry_id": "760097843905",
                "repository_name": "uk.ac.wellcome/id_minter",
                "image_tag": "env.2022-08-24",
            },
        )
    ],
)
def test_parse_ecr_image_uri(image_uri, expected_result):
    assert ecr.parse_ecr_image_uri(image_uri) == expected_result
