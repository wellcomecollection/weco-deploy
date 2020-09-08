FROM python:3.7-alpine

LABEL maintainer = "Wellcome Collection <dev@wellcomecollection.org>"
LABEL description = "A Docker image for deploying our Python/Tox images to AWS"

RUN apk update && \
    apk add docker git build-base libffi-dev openssl-dev openssh-client

RUN pip install awscli setuptools tox

VOLUME /workdir
WORKDIR /workdir

ENTRYPOINT ["tox"]
