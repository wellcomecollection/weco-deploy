# -*- encoding: utf-8 -*-
"""Command running functions"""

import shlex
import subprocess
import sys


def cmd(*args):
    return subprocess.check_output(list(args)).decode("utf8").strip()


def ensure(command):
    try:
        subprocess.check_call(shlex.split(command))
    except subprocess.CalledProcessError as err:
        sys.exit(err.returncode)


def configure_aws_profile(role_arn, profile_name):
    cmd('aws', 'configure', 'set', 'region', "eu-west-1", '--profile', profile_name)  # noqa: E501
    cmd('aws', 'configure', 'set', 'role_arn', role_arn, '--profile', profile_name)   # noqa: E501
    cmd('aws', 'configure', 'set', 'source_profile', 'default', '--profile', profile_name)  # noqa: E501
