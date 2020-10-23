from base64 import b64decode
import os

from botocore.exceptions import ClientError

from .exceptions import EcrError
from .iam import Iam
from .commands import cmd


class EcrImage:
    """
    Convenience wrapper around a response from the ECR DescribeImages API.
    """
    def __init__(self, ecr_base_uri, repository_name, tag, describe_images_resp):
        if not describe_images_resp["imageDetails"]:
            raise EcrError(f"No matching images found for {repository_name}:{tag}!")

        if len(describe_images_resp["imageDetails"]) > 1:
            raise EcrError(f"Multiple matching images found for {repository_name}:{tag}!")

        self._image_details = describe_images_resp["imageDetails"][0]
        self.ecr_base_uri = ecr_base_uri
        self.repository_name = repository_name
        self.tag = tag

    @property
    def tags(self):
        return set(self._image_details["imageTags"])

    def ref_uri(self):
        ref_tags = {t for t in self.tags if t.startswith("ref.")}

        if not ref_tags:
            raise EcrError(f"No matching ref tags found for {self.repository_name}:{self.tag}!")

        # It's possible to get multiple ref tags if the same image is published
        # at different Git commits, but there are no code changes for this image
        # between the two commits.  If so, choose one arbitrarily.
        ref = ref_tags.pop()

        return f"{self.ecr_base_uri}/{self.repository_name}:{ref}"


class Ecr:
    def __init__(self, account_id, region_name, role_arn):
        self.account_id = account_id
        self.region_name = region_name
        self.session = Iam.get_session(
            session_name="ReleaseToolEcr",
            role_arn=role_arn,
            region_name=region_name
        )
        self.ecr = self.session.client('ecr')

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

    def describe_image(self, namespace, image_id, tag, account_id=None):
        repository_name = Ecr._get_repository_name(namespace, image_id)
        if not account_id:
            account_id = self.account_id

        result = self.ecr.describe_images(
            registryId=account_id,
            repositoryName=repository_name,
            imageIds=[
                {"imageTag": tag}
            ]
        )

        image = EcrImage(
            ecr_base_uri=self.ecr_base_uri,
            repository_name=repository_name,
            tag=tag,
            describe_images_resp=result
        )

        return {
            'repository_name': repository_name,
            'image_id': image_id,
            'ref': image.ref_uri(),
        }

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
