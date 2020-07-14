import os

from botocore.exceptions import ClientError

from .iam import Iam
from .commands import cmd, ensure


class Ecr:
    def __init__(self, account_id, region_id, role_arn=None):
        self.account_id = account_id
        self.region_id = region_id
        self.session = Iam.get_session("ReleaseToolEcr", role_arn)
        self.ecr = self.session.client('ecr')

        self.ecr_base_uri = (
            f"{self.account_id}.dkr.ecr.{self.region_id}.amazonaws.com"
        )

    @staticmethod
    def _get_release_image_tag(service_id):
        repo_root = cmd("git", "rev-parse", "--show-toplevel")
        release_file = os.path.join(repo_root, ".releases", service_id)

        return open(release_file).read().strip()

    @staticmethod
    def _get_repository_name(namespace, service_id):
        return f"{namespace}/{service_id}"

    def _get_full_repository_uri(self, namespace, service_id, tag):
        return f"{self.ecr_base_uri}/{Ecr._get_repository_name(namespace, service_id)}:{tag}"

    def publish_image(self, namespace, service_id, dry_run=False):
        local_image_tag = Ecr._get_release_image_tag(service_id)
        local_image_name = f"{service_id}:{local_image_tag}"

        remote_image_tag = f"ref.{local_image_tag}"
        remote_image_name = self._get_full_repository_uri(namespace, service_id, remote_image_tag)

        if not dry_run:
            try:
                cmd('docker', 'tag', local_image_name, remote_image_name)
                cmd('docker', 'push', remote_image_name)

            finally:
                cmd('docker', 'rmi', remote_image_name)

        return remote_image_name, remote_image_tag, local_image_tag

    def describe_image(self, namespace, service_id, tag, account_id=None):
        repository_name = Ecr._get_repository_name(namespace, service_id)
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
            service_id,
            env_tag
        ) for env_tag in env_tags}

        refs = [self._get_full_repository_uri(namespace, service_id, ref_tag) for ref_tag in ref_tags]

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
            'service_id': service_id,
            'envs': envs,
            'ref': ref
        }

    def retag_image(self, namespace, service_id, tag, new_tag, dry_run=False):
        repository_name = Ecr._get_repository_name(namespace, service_id)

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

        if not dry_run:
            try:
                result = self.ecr.put_image(
                    registryId=self.account_id,
                    repositoryName=repository_name,
                    imageTag=new_tag,
                    imageManifest=image['imageManifest']
                )
            except ClientError as e:
                # Matching tag & digest already exists (nothing to do)
                if not e.response['Error']['Code'] == 'ImageAlreadyExistsException':
                    raise e

    def login(self, profile_name=None):
        base = ['aws', 'ecr', 'get-login']
        login_options = ['--no-include-email', '--registry-ids', self.account_id]
        profile_options = ['--profile', profile_name]

        if profile_name:
            login = base + profile_options + login_options
        else:
            login = base + login_options

        ensure(cmd(*login))
