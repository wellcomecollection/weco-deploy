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

    @staticmethod
    def _get_release_image_tag(service_id):
        repo_root = cmd("git", "rev-parse", "--show-toplevel")
        release_file = os.path.join(repo_root, ".releases", service_id)

        print(f"*** Retrieving image tag for {service_id} from {release_file}")

        return open(release_file).read().strip()

    def publish_image(self, namespace, service_id, label, dry_run=False):
        # some terminology as label & tag are confusing
        # - label is a given label relating to deployment e.g. latest, prod, stage
        # - image_tag is usually the git ref, denoting a particular build artifact

        image_tag = Ecr._get_release_image_tag(service_id)

        label_image_name = f"{service_id}:{label}"
        tag_image_name = f"{service_id}:{image_tag}"

        base_remote_image_name = (
            f"{self.account_id}.dkr.ecr.{self.region_id}.amazonaws.com/{namespace}"
        )

        remote_label_image_name = f"{base_remote_image_name}/{label_image_name}"
        remote_tag_image_name = f"{base_remote_image_name}/{tag_image_name}"

        if not dry_run:
            try:
                print(f"*** Pushing {label_image_name} to {remote_label_image_name}")
                cmd('docker', 'tag', label_image_name, remote_label_image_name)
                cmd('docker', 'push', remote_label_image_name)

                print(f"*** Pushing {tag_image_name} to {remote_tag_image_name}")
                cmd('docker', 'tag', tag_image_name, remote_tag_image_name)
                cmd('docker', 'push', remote_tag_image_name)

            finally:
                cmd('docker', 'rmi', label_image_name)
                cmd('docker', 'rmi', tag_image_name)

        return remote_tag_image_name

    def retag_image(self, namespace, service_id, tag, new_tag, dry_run=False):
        repository_name = f"{namespace}/{service_id}"

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
                self.ecr.put_image(
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
