FROM public.ecr.aws/docker/library/python:3.9-alpine

LABEL maintainer = "Wellcome Collection <dev@wellcomecollection.org>"
LABEL description = "A Docker image for deploying our Docker images to AWS"

RUN apk update && \
    apk add docker git openssh

RUN pip install awscli

ADD . /weco-deploy
RUN pip install -e /weco-deploy

VOLUME /repo
WORKDIR /repo

ENTRYPOINT ["weco-deploy"]
