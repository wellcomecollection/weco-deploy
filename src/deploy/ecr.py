from base64 import b64decode
import os

from botocore.exceptions import ClientError

from . import iam
from .exceptions import EcrError
from .commands import cmd


def create_client(*, account_id, region_name, role_arn):
    session = iam.get_session(
        session_name="ReleaseToolEcr",
        role_arn=role_arn,
        region_name=region_name
    )

    return session.client("ecr")


class Ecr:
    def __init__(self, account_id, region_name, role_arn):
        self.account_id = account_id
        self.region_name = region_name
        self.ecr = create_client(
            account_id=account_id,
            region_name=region_name,
            role_arn=role_arn
        )

        self.ecr_base_uri = (
            f"{self.account_id}.dkr.ecr.{self.region_name}.amazonaws.com"
        )

    @staticmethod
    def _get_release_image_tag(image_id):
        repo_root = cmd("git", "rev-parse", "--show-toplevel")
        release_file = os.path.join(repo_root, ".releases", image_id)

        return open(release_file).read().strip()

    @staticmethod
    def _get_repository_name(namespace, image_id):
        return f"{namespace}/{image_id}"

    def _get_full_repository_uri(self, namespace, image_id, tag):
        return f"{self.ecr_base_uri}/{Ecr._get_repository_name(namespace, image_id)}:{tag}"

    def publish_image(self, namespace, image_id):
        local_image_tag = Ecr._get_release_image_tag(image_id)
        local_image_name = f"{image_id}:{local_image_tag}"

        remote_image_tag = f"ref.{local_image_tag}"
        remote_image_name = self._get_full_repository_uri(namespace, image_id, remote_image_tag)

        try:
            cmd('docker', 'tag', local_image_name, remote_image_name)
            cmd('docker', 'push', remote_image_name)

        finally:
            cmd('docker', 'rmi', remote_image_name)

        return remote_image_name, remote_image_tag, local_image_tag

    def tag_image(self, namespace, image_id, tag, new_tag):
        repository_name = Ecr._get_repository_name(namespace, image_id)

        result = self.ecr.batch_get_image(
            registryId=self.account_id,
            repositoryName=repository_name,
            imageIds=[
                {"imageTag": tag}
            ]
        )

        if len(result["images"]) == 0:
            raise RuntimeError(f"No matching images found for {repository_name}:{tag}!")

        if len(result["images"]) > 1:
            raise RuntimeError(f"Multiple matching images found for {repository_name}:{tag}!")

        image = result["images"][0]

        tag_operation = {
            'source': f"{repository_name}:{tag}",
            'target': f"{repository_name}:{new_tag}"
        }

        try:
            self.ecr.put_image(
                registryId=self.account_id,
                repositoryName=repository_name,
                imageTag=new_tag,
                imageManifest=image['imageManifest']
            )

            tag_operation_status = "success"
        except ClientError as e:
            # Matching tag & digest already exists (nothing to do)
            if not e.response['Error']['Code'] == 'ImageAlreadyExistsException':
                raise e
            else:
                tag_operation_status = "noop"

        tag_operation['status'] = tag_operation_status

        return tag_operation

    def login(self):
        response = self.ecr.get_authorization_token(
            registryIds=[self.account_id]
        )

        for auth in response['authorizationData']:
            auth_token = b64decode(auth['authorizationToken']).decode()
            username, password = auth_token.split(':')
            command = ['docker', 'login', '-u', username, '-p', password, auth['proxyEndpoint']]

            cmd(*command)


class NoSuchImageError(EcrError):
    """
    Raised when an image cannot be found.
    """
    pass


class NoRefTagError(EcrError):
    """
    Raised when an image does not have any tags starting ``ref.``.
    """
    pass


def get_ref_tags_for_image(ecr_client, *, repository_name, tag, account_id):
    """
    Returns the ref tags for the image with this tag.

    e.g. if you look for the "latest" tag, it will return the unambiguous Git ref tag(s)
    for this image.
    """
    try:
        resp = ecr_client.describe_images(
            registryId=account_id,
            repositoryName=repository_name,
            imageIds=[{"imageTag": tag}],
        )
    except ClientError as e:
        if not e.response["Error"]["Code"] == "ImageNotFoundException":
            raise e
        else:
            raise NoSuchImageError(
                f"Cannot find an image in {repository_name} with tag {tag}"
            )

    assert len(resp["imageDetails"]) == 1, resp
    image_details = resp["imageDetails"][0]

    tags = set(image_details["imageTags"])
    ref_tags = {t for t in tags if t.startswith("ref.")}

    if not ref_tags:
        raise NoRefTagError(
            f"No matching ref tags found for {repository_name}:{tag}!"
        )

    return ref_tags


def get_ref_tags_for_repositories(*, image_repositories, tag):
    """
    Returns the ref tags for all the repositories in ``image_repositories``.

    Repositories should be a dict of the form:

        (id) -> {
            "account_id": (account_id),
            "region_name": (region_name),
            "role_arn": (role_arn),
            "repository_name": (repository_name),
        }

    Returns a dict (id) -> set(ref_tags)

    """
    result = {}

    for repo_id, repo_details in image_repositories.items():
        account_id = repo_details["account_id"]
        region_name = repo_details["region_name"]
        role_arn = repo_details["role_arn"]

        ecr_client = create_client(
            account_id=account_id,
            region_name=region_name,
            role_arn=role_arn
        )

        try:
            ref_uri = get_ref_tags_for_image(
                ecr_client,
                repository_name=repo_details["repository_name"],
                tag=tag,
                account_id=account_id
            )
        except NoSuchImageError:
            result[repo_id] = set()
        else:
            result[repo_id] = ref_uri

    return result
