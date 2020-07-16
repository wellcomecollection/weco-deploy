# -*- encoding: utf-8 -*-
"""Command running functions"""

import subprocess
import sys


def cmd(*args):
    try:
        return subprocess.check_output(list(args)).decode("utf8").strip()
    except subprocess.CalledProcessError as err:
        sys.exit(err.returncode)
