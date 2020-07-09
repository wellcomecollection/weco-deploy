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
    if os.getenv("TRAVIS_EVENT_TYPE", "unset") == "push":
        task = "publish"
    else:
        task = "build"

    # Log in to Docker Hub.  Be careful about this subprocess call -- if it
    # errors, the default exception would print our password to stderr.
    # See https://alexwlchan.net/2018/05/beware-logged-errors/
    if task == "publish":
        try:
            subprocess.check_call([
                "docker", "login",
                "--username", "wellcometravis",
                "--password", os.environ["DOCKER_HUB_PASSWORD"]
            ])
        except subprocess.CalledProcessError as err:
            sys.exit("Error trying to authenticate with Docker Hub: %r" % err)

    image_name = "wellcome/%s:%s" % (NAME, tools.latest_version())

    subprocess.check_call([
        "docker", "build",
        "--tag", image_name, ROOT
    ])

    if not tools.has_release():
        print('Not deploying due to no release')
        sys.exit(0)

    try:
        if task == "publish":
            tools.git('fetch')

            subprocess.check_call([
                "docker", "build",
                "--tag", image_name, ROOT
            ])
            subprocess.check_call(["docker", "push", image_name])
        else:
            print("Not publishing!")
    except subprocess.CalledProcessError as err:
        print("ERROR: %r" % err)
        sys.exit(1)
