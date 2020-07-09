# -*- encoding: utf-8 -*-
"""Publish specific logic"""

import os

import boto3

from .commands import cmd, ensure


def _get_release_image_tag(service_id):
    repo_root = cmd("git", "rev-parse", "--show-toplevel")
    release_file = os.path.join(repo_root, ".releases", service_id)

    print(f"*** Retrieving image tag for {service_id} from {release_file}")

    return open(release_file).read().strip()


def publish_image(account_id, namespace, service_id, label, region_id):
    # some terminology as label & tag are confusing
    # - label is a given label relating to deployment e.g. latest, prod, stage
    # - image_tag is usually the git ref, denoting a particular build artifact

    image_tag = _get_release_image_tag(service_id)

    label_image_name = f"{service_id}:{label}"
    tag_image_name = f"{service_id}:{image_tag}"

    base_remote_image_name = (
        f"{account_id}.dkr.ecr.{region_id}.amazonaws.com/{namespace}"
    )

    remote_label_image_name = f"{base_remote_image_name}/{label_image_name}"
    remote_tag_image_name = f"{base_remote_image_name}/{tag_image_name}"

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

    return tag_image_name


def ecr_login(account_id, profile_name):
    print(f"*** Authenticating {account_id} for `docker push` with ECR")

    base = ['aws', 'ecr', 'get-login']
    login_options = ['--no-include-email', '--registry-ids', account_id]
    profile_options = ['--profile', profile_name]

    if profile_name:
        login = base + profile_options + login_options
    else:
        login = base + login_options

    ensure(cmd(*login))


def update_ssm(project_id, service_id, label, remote_image_name, profile_name):
    ssm_path = f"/{project_id}/images/{label}/{service_id}"

    print(f"*** Updating SSM path {ssm_path} to {remote_image_name}")

    if profile_name:
        session = boto3.Session(profile_name=profile_name)
        ssm_client = session.client('ssm')
    else:
        ssm_client = boto3.client('ssm')

    ssm_client.put_parameter(
        Name=f"/{project_id}/images/{label}/{service_id}",
        Description=f"Docker image URL; auto-managed by {__file__}",
        Value=remote_image_name,
        Type="String",
        Overwrite=True
    )
