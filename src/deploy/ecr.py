from abc import ABC, abstractmethod
import base64
import json
import os

from botocore.exceptions import ClientError

from . import iam
from .exceptions import EcrError
from .commands import cmd


def create_client(*, region_name, role_arn):
    session = iam.get_session(
        session_name="ReleaseToolEcr",
        role_arn=role_arn,
        region_name=region_name
    )

    return session.client("ecr")


def _get_repository_name(namespace, image_id):
    if namespace:
        return f"{namespace}/{image_id}"
    else:
        return image_id


class AbstractEcr(ABC):
    def __init__(self, *, resource):
        self.resource = resource

    @abstractmethod
    def base_uri(self):
        pass

    def get_image_uri(self, *, namespace, image_id, tag):
        repository_name = _get_repository_name(namespace, image_id)
        return f"{self.base_uri}/{repository_name}:{tag}"

    def create_client(self, *, region_name, role_arn):
        session = iam.get_session(
            session_name="ReleaseToolEcr",
            role_arn=role_arn,
            region_name=region_name
        )

        return session.client(self.resource)

    @abstractmethod
    def get_authorization_data(self):
        """
        Returns an "authorization token data object" that can be used to
        authenticate with the local Docker client.
        """
        pass

    def login(self):
        """
        Authenticates the local Docker client with ECR.
        """
        auth_data = self.get_authorization_data()
        auth_token = base64.b64decode(auth_data["authorizationToken"]).decode()
        username, password = auth_token.split(":")
        command = [
            "docker", "login", "--username", username, "--password", password,
            auth_data["proxyEndpoint"]
        ]

        cmd(*command)

    @abstractmethod
    def get_image_manifests_for_tag(self, *, repository_name, image_tag):
        """
        Generates a list of image manifests for a given tag.
        """
        pass


class EcrPrivate(AbstractEcr):
    def __init__(self, *, account_id, region_name, role_arn):
        super().__init__(resource="ecr")

        self.region_name = region_name
        self.account_id = account_id
        self.client = self.create_client(
            region_name=region_name,
            role_arn=role_arn
        )

    @property
    def base_uri(self):
        return f"{self.account_id}.dkr.ecr.{self.region_name}.amazonaws.com"

    @property
    def registry_id(self):
        return self.account_id

    def get_authorization_data(self):
        resp = self.client.get_authorization_token(
            registryIds=[self.account_id]
        )
        assert len(resp["authorizationData"]) == 1
        return resp["authorizationData"][0]

    def get_image_manifests_for_tag(self, *, repository_name, image_tag):
        resp = self.client.batch_get_image(
            registryId=self.registry_id,
            repositoryName=repository_name,
            imageIds=[{"imageTag": image_tag}]
        )

        return [img["imageManifest"] for img in resp["images"]]


class EcrPublic(AbstractEcr):
    def __init__(self, *, gallery_id, role_arn):
        super().__init__(resource="ecr-public")

        self.gallery_id = gallery_id

        self.client = self.create_client(
            role_arn=role_arn,
            # ECR Public is a global resource that lives in us-east-1,
            # as far as I can tell.
            region_name="us-east-1"
        )

    @property
    def base_uri(self):
        return f"public.ecr.aws/{self.gallery_id}"

    def get_authorization_data(self):
        resp = self.client.get_authorization_token()
        return resp["authorizationData"]

    def get_image_manifests_for_tag(self, *, repository_name, image_tag):
        # ECR Public doesn't have an API call that returns the image manifest,
        # so we have to go out to an experimental Docker feature.
        # See https://docs.docker.com/engine/reference/commandline/manifest/
        uri = f"public.ecr.aws/{self.gallery_id}/{repository_name}"
        output = json.loads(cmd("docker", "manifest", "inspect", uri))

        return [output]


class Ecr:
    def __init__(self, account_id, region_name, role_arn):
        self.account_id = account_id
        self.region_name = region_name
        self.ecr = create_client(region_name=region_name, role_arn=role_arn)

        self.ecr_base_uri = (
            f"{self.account_id}.dkr.ecr.{self.region_name}.amazonaws.com"
        )

        self._underlying = EcrPrivate(
            account_id=account_id,
            region_name=region_name,
            role_arn=role_arn
        )

    @staticmethod
    def _get_release_image_tag(image_id):
        repo_root = cmd("git", "rev-parse", "--show-toplevel")
        release_file = os.path.join(repo_root, ".releases", image_id)

        return open(release_file).read().strip()

    def publish_image(self, namespace, image_id):
        local_image_tag = Ecr._get_release_image_tag(image_id)
        local_image_name = f"{image_id}:{local_image_tag}"

        remote_image_tag = f"ref.{local_image_tag}"
        remote_image_name = self._underlying.get_image_uri(
            namespace=namespace,
            image_id=image_id,
            tag=remote_image_tag
        )

        try:
            cmd('docker', 'tag', local_image_name, remote_image_name)
            cmd('docker', 'push', remote_image_name)

        finally:
            cmd('docker', 'rmi', remote_image_name)

        return remote_image_name, remote_image_tag, local_image_tag

    def tag_image(self, namespace, image_id, tag, new_tag):
        repository_name = _get_repository_name(namespace, image_id)

        manifests = self._underlying.get_image_manifests_for_tag(
            repository_name=repository_name,
            image_tag=tag
        )

        if len(manifests) == 0:
            raise RuntimeError(f"No matching images found for {repository_name}:{tag}!")

        if len(manifests) > 1:
            raise RuntimeError(f"Multiple matching images found for {repository_name}:{tag}!")

        existing_manifest = manifests[0]

        tag_operation = {
            'source': f"{repository_name}:{tag}",
            'target': f"{repository_name}:{new_tag}"
        }

        try:
            self.ecr.put_image(
                registryId=self.account_id,
                repositoryName=repository_name,
                imageTag=new_tag,
                imageManifest=existing_manifest
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
        self._underlying.login()


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
            "namespace": (namespace) or None,
        }

    Returns a dict (id) -> set(ref_tags)

    """
    result = {}

    for repo_id, repo_details in image_repositories.items():
        account_id = repo_details["account_id"]
        region_name = repo_details["region_name"]
        role_arn = repo_details["role_arn"]
        namespace = repo_details.get("namespace", None)
        repository_name = _get_repository_name(namespace, repo_id)

        ecr_client = create_client(region_name=region_name, role_arn=role_arn)

        try:
            ref_uri = get_ref_tags_for_image(
                ecr_client,
                repository_name=repository_name,
                tag=tag,
                account_id=account_id
            )
        except NoSuchImageError:
            result[repo_id] = set()
        else:
            result[repo_id] = ref_uri

    return result
