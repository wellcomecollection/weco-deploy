FROM python:3.7-alpine

LABEL maintainer = "Wellcome Collection <dev@wellcomecollection.org>"
LABEL description = "A Docker image for deploying our Docker images to AWS"

RUN apk update && \
    apk add docker git

ADD . /weco-deploy
RUN pip install -e /weco-deploy

VOLUME /repo
WORKDIR /repo

ENTRYPOINT ["weco-deploy"]
