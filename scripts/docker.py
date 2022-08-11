#!/usr/bin/env python
# -*- encoding: utf-8
"""
This script runs in Travis to build/publish our Docker images.

If this script runs in a pull request, it just checks the images can
build successfully.

If this script runs in a push to main, it builds the images and then
publishes them to Docker Hub.

It exits with code 0 (success) if the build/publish was successful,
or code 1 (failure) if the build/publish fails for any image.
"""

import subprocess
import sys

import hypothesistooling as tools


ROOT = subprocess.check_output([
    "git", "rev-parse", "--show-toplevel"]).decode("utf8").strip()

NAME = "weco-deploy"


def docker(*args):
    subprocess.check_call(["docker"] + list(args))


if __name__ == '__main__':
    tools.git('config', 'user.name', 'Buildkite on behalf of Wellcome Collection')
    tools.git('config', 'user.email', 'wellcomedigitalplatform@wellcome.ac.uk')
    tools.add_ssh_origin()

    # Get latest metadata (can't pull here as need to keep RELEASE.rst to signify release)
    tools.git('fetch')

    HEAD = tools.hash_for_name('HEAD')
    MAIN = tools.hash_for_name('origin/main')

    on_main = tools.is_ancestor(HEAD, MAIN)
    has_release = tools.has_release()

    major, minor, patch = tuple(map(int, tools.latest_version().split(".")))
    tags = [
        f"{major}.{minor}.{patch}",
        f"{major}.{minor}",
        f"{major}",
    ]
    image_names = ["wellcome/%s:%s" % (NAME, tag) for tag in tags]
    local_image_name = image_names[0]

    # Get latest code before we build
    tools.git('pull', 'origin', 'main')

    docker("build", "--tag", local_image_name, ROOT)

    if on_main:
        try:
            for image_name in image_names:
                docker("tag", local_image_name, image_name)
                docker("push", image_name)

                ecr_image_name = "760097843905.dkr.ecr.eu-west-1.amazonaws.com/%s" % image_name
                docker("tag", local_image_name, ecr_image_name)
                docker("push", ecr_image_name)

        except subprocess.CalledProcessError as err:
            print("ERROR: %r" % err)
            sys.exit(1)
    else:
        print('Not publishing due to no release')
        sys.exit(0)
