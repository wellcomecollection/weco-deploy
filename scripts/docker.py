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


def print_banner(action, name):
    """
    Prints a coloured banner to stdout.
    """
    # The escape codes \033[92m and \033[0m are for printing in colour.
    # See: https://stackoverflow.com/a/287944/1558022
    print("\033[92m*** %s %s ***\033[0m" % ((action + ":").ljust(10), name))


if __name__ == '__main__':
    publish_in_dev = os.getenv("PUBLISH", "unset")

    if os.getenv("TRAVIS_EVENT_TYPE", "unset") == "push":
        task = "publish"
    elif publish_in_dev != "unset":
        task = "local_publish"

        local_publish = dict.fromkeys(
            publish_in_dev.split(","), 1
        )
    else:
        task = "build"

    # Images get tagged with their Travis build number -- which should be
    # a monotonically increasing sequence, so we can easily see which image
    # is "newest".
    build_tag = tools.__version__

    results = {}

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

    image_name = "wellcome/%s:%s" % (NAME, build_tag)

    try:
        subprocess.check_call(["docker", "build", "--tag", image_name, ROOT])
        do_local_publish = task == "local_publish"

        if task == "publish" or do_local_publish:
            subprocess.check_call(["docker", "push", image_name])
    except subprocess.CalledProcessError as err:
        print("ERROR: %r" % err)
        sys.exit(1)
