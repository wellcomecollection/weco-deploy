FROM public.ecr.aws/docker/library/python:3.7-alpine

LABEL maintainer = "Wellcome Collection <dev@wellcomecollection.org>"
LABEL description = "A Docker image for deploying our Python/Tox images to AWS"

RUN apk add --update docker git build-base libffi-dev openssl-dev openssh openssh-client openrc

# Install the Rust compiler toolchain required to install cryptography
# from the requirements for weco-deploy
# See https://cryptography.io/en/latest/installation.html#alpine
RUN apk add --update gcc musl-dev python3-dev libffi-dev openssl-dev cargo
RUN pip install cryptography

RUN rc-update add sshd

RUN pip install --upgrade pip awscli setuptools tox

VOLUME /workdir
WORKDIR /workdir

ENTRYPOINT ["tox"]
