#!/usr/bin/env python3

import os

from setuptools import setup
from setuptools import find_packages


def local_file(name):
    return os.path.relpath(os.path.join(os.path.dirname(__file__), name))


SOURCE = local_file('src')
README = local_file('README.md')

long_description = open(README).read()

# Assignment to placate pyflakes. The actual version is from the exec that
# follows.
__version__ = None

install_requires = [
    'click >= 7.1.2',
]

setup(
    name='weco-deploy',
    version=__version__,
    description='A tool for deploying ECS services at the Wellcome Collection',
    long_description=long_description,
    url='https://github.com/wellcomecollection/weco-deploy',
    author='Wellcome Collection',
    author_email='wellcomedigitalplatform@wellcome.ac.uk',
    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Other Audience',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    packages=find_packages(SOURCE),
    package_dir={'': SOURCE},
    install_requires=install_requires,

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
        'console_scripts': [
            'weco-deploy=deploy:main',
        ],
    },
)