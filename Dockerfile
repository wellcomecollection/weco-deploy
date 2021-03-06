FROM 760097843905.dkr.ecr.eu-west-1.amazonaws.com/python:3.7-alpine

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
