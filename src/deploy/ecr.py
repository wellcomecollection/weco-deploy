from base64 import b64decode
import os

from botocore.exceptions import ClientError

from .iam import Iam
from .commands import cmd


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

        if len(result['imageDetails']) == 0:
            raise RuntimeError(f"No matching images found for {repository_name}:{tag}!")

        if len(result['imageDetails']) > 1:
            raise RuntimeError(f"Multiple matching images found for {repository_name}:{tag}!")

        image_details = result['imageDetails'][0]

        is_latest = 'latest' in image_details['imageTags']

        ref_tags = [image for image in image_details['imageTags'] if image.startswith("ref.")]
        env_tags = [image for image in image_details['imageTags'] if image.startswith("env.")]

        envs = {env_tag.split('.')[-1]: self._get_full_repository_uri(
            namespace,
            image_id,
            env_tag
        ) for env_tag in env_tags}

        refs = [self._get_full_repository_uri(namespace, image_id, ref_tag) for ref_tag in ref_tags]

        # It is possible multiple ref tags can occur if images are published at new git refs with
        # no image changes, deal with it gracefully - just get the first
        if len(refs) < 1:
            raise RuntimeError(f"No matching ref tags found for {repository_name}:{tag}!")
        ref = refs[0]

        return {
            'registry_id': image_details['registryId'],
            'repository_name': image_details['repositoryName'],
            'image_digest': image_details['imageDigest'],
            'is_latest': is_latest,
            'image_id': image_id,
            'envs': envs,
            'ref': ref
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
