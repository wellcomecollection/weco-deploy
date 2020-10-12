#!/usr/bin/env python
# -*- encoding: utf-8
"""
This script runs in Travis to build/publish our Docker images.

If this script runs in a pull request, it just checks the images can
build successfully.

If this script runs in a push to master, it builds the images and then
publishes them to Docker Hub.

It exits with code 0 (success) if the build/publish was successful,
or code 1 (failure) if the build/publish fails for any image.
"""

import os
import subprocess
import sys

import hypothesistooling as tools


ROOT = subprocess.check_output([
    "git", "rev-parse", "--show-toplevel"]).decode("utf8").strip()

NAME = "weco-deploy"


if __name__ == '__main__':
    tools.git('config', 'user.name', 'Buildkite on behalf of Wellcome Collection')
    tools.git('config', 'user.email', 'wellcomedigitalplatform@wellcome.ac.uk')
    tools.add_ssh_origin()
    tools.git('fetch')

    HEAD = tools.hash_for_name('HEAD')
    MASTER = tools.hash_for_name('origin/master')

    on_master = tools.is_ancestor(HEAD, MASTER)
    has_release = tools.has_release()

    image_name = "wellcome/%s:%s" % (NAME, tools.latest_version())

    subprocess.check_call([
        "docker", "build",
        "--tag", image_name, ROOT
    ])

    if has_release and on_master:
        # Log in to Docker Hub & push.  Be careful about this subprocess call -- if it
        # errors, the default exception would print our password to stderr.
        # See https://alexwlchan.net/2018/05/beware-logged-errors/
        try:
            subprocess.check_call([
                "docker", "login",
                "--username", "wellcometravis",
                "--password", os.environ["DOCKER_HUB_PASSWORD"]
            ])

            subprocess.check_call([
                "docker", "build",
                "--tag", image_name, ROOT
            ])

            subprocess.check_call(["docker", "push", image_name])
        except subprocess.CalledProcessError as err:
            print("ERROR: %r" % err)
            sys.exit(1)
    else:
        print('Not publishing due to no release')
        sys.exit(0)
