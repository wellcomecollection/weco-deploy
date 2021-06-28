#!/usr/bin/env python

# coding=utf-8
#
# This file is part of Hypothesis, which may be found at
# https://github.com/HypothesisWorks/hypothesis-python
#
# Most of this work is copyright (C) 2013-2017 David R. MacIver
# (david@drmaciver.com), but it contains contributions by others. See
# CONTRIBUTING.rst for a full list of people who may hold copyright, and
# consult the git log if you need to determine who owns an individual
# contribution.
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at http://mozilla.org/MPL/2.0/.
#
# END HEADER

from __future__ import division, print_function, absolute_import

import os
import sys
import shutil
import subprocess

import hypothesistooling as tools

sys.path.append(os.path.dirname(__file__))  # noqa


DIST = os.path.join(tools.ROOT, 'dist')


PENDING_STATUS = ('started', 'created')


if __name__ == '__main__':
    last_release = tools.latest_version()

    print('Current version: %s. Latest released version: %s' % (
        tools.__version__, last_release
    ))

    tools.add_ssh_origin()
    tools.git("fetch", "ssh-origin")

    HEAD = tools.hash_for_name('HEAD')
    MAIN = tools.hash_for_name('ssh-origin/main')
    print('Current head:  ', HEAD)
    print('Current main:', MAIN)

    on_main = tools.is_ancestor(HEAD, MAIN)
    has_release = tools.has_release()

    if has_release:
        print('Updating changelog and version')
        tools.update_for_pending_release()

    print('Building an sdist...')

    if os.path.exists(DIST):
        shutil.rmtree(DIST)

    subprocess.check_call([
        sys.executable, 'setup.py', 'sdist', '--dist-dir', DIST,
    ])

    if not on_main:
        print('Not deploying due to not being on main')
        sys.exit(0)

    if not has_release:
        print('Not deploying due to no release')
        sys.exit(0)

    print('Release seems good. Pushing to GitHub now.')

    tools.create_tag_and_push()

    print('Now uploading to pypi.')

    try:
        subprocess.check_call([
            sys.executable, '-m', 'twine', 'upload',
            '--username', os.environ['PYPI_USERNAME'],
            '--password', os.environ['PYPI_PASSWORD'],
            os.path.join(DIST, '*'),
        ])
    except subprocess.CalledProcessError as err:
        print("ERROR: %r" % err)
        sys.exit(1)

    sys.exit(0)
