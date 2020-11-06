import hashlib
from random import random


# Taken from https://github.com/rubelw/mymoto/blob/e43ef43db676058d08855588dd52419a3554e336/moto/tests/test_ecr/test_ecr_boto3.py#L18-L21
def _create_image_digest(contents=None):
    if not contents:
        contents = "docker_image{0}".format(int(random() * 10 ** 6))
    return "sha256:%s" % hashlib.sha256(contents.encode("utf-8")).hexdigest()


# Taken from https://github.com/rubelw/mymoto/blob/e43ef43db676058d08855588dd52419a3554e336/moto/tests/test_ecr/test_ecr_boto3.py#L24-L52
def create_image_manifest():
    return {
        "schemaVersion": 2,
        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
        "config": {
            "mediaType": "application/vnd.docker.container.image.v1+json",
            "size": 7023,
            "digest": _create_image_digest("config"),
        },
        "layers": [
            {
                "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
                "size": 32654,
                "digest": _create_image_digest("layer1"),
            },
            {
                "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
                "size": 16724,
                "digest": _create_image_digest("layer2"),
            },
            {
                "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
                "size": 73109,
                # randomize image digest
                "digest": _create_image_digest(),
            },
        ],
    }
