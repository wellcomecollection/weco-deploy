# -*- encoding: utf-8 -*-
"""Command running functions"""

from subprocess import run, check_output, PIPE, CalledProcessError
import sys


def cmd(*args):
    try:
        return check_output(list(args)).decode("utf8").strip()
    except CalledProcessError as err:
        sys.exit(err.returncode)


def stdin_to_cmd(stdin, *args):
    try:
        proc = run(list(args), stdout=PIPE, input=stdin, encoding='utf8')
        return proc.stdout.strip()
    except CalledProcessError as err:
        sys.exit(err.returncode)