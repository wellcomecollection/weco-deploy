#!/usr/bin/env bash

set -o errexit
set -o nounset

git config user.name "Buildkite on behalf of Wellcome Collection"
git config user.email "wellcomedigitalplatform@wellcome.ac.uk"
git remote add ssh-origin "git@github.com:wellcomecollection/weco-deploy.git"

if [[ ! -f RELEASE.md ]]
then
  echo "Not publishing because there's no RELEASE.md"
  exit 0
fi

# Get the latest metadata about origin/main
git fetch

HEAD=$(git rev-parse HEAD)
MAIN=$(git rev-parse origin/main)

git merge-base --is-ancestor HEAD MAIN && ON_MAIN=$? || ON_MAIN=$?

# if (( ON_MAIN == 1 ))
# then
#   echo "Not publishing because we're not on main"
#   exit 0
# fi

LATEST_TAG=$(git describe --tags --abbrev=0)
echo "Latest tag is $LATEST_VERSION"

LATEST_TAG="wellcome/weco-deploy:$LATEST_TAG"

MAJOR_TAG=$(echo "$LATEST_VERSION" | tr '.' ' ' | awk '{print $1}')
MINOR_TAG=$(echo "$LATEST_VERSION" | tr '.' ' ' | awk '{print $2}')
PATCH_TAG=$(echo "$LATEST_VERSION" | tr '.' ' ' | awk '{print $3}')

VERSION_TAGS="
  $MAJOR_TAG
  $MAJOR_TAG.$MINOR_TAG
  $MAJOR_TAG.$MINOR_TAG.$PATCH_TAG
  latest"

docker build --tag "$LATEST_TAG" .

docker login --username wellcometravis --password "$DOCKER_HUB_PASSWORD"
for version in $VERSION_TAGS
do
  docker tag "$LATEST_TAG" "wellcome/weco-deploy:$tag"
  docker push "wellcome/weco-deploy:$tag"
done

eval $(aws ecr get-login --no-include-email)
for version in $VERSION_TAGS
do
  docker tag "$LATEST_TAG" "760097843905.dkr.ecr.eu-west-1.amazonaws.com/$LATEST_TAG"
  docker push "760097843905.dkr.ecr.eu-west-1.amazonaws.com/$LATEST_TAG"
done

aws ecr-public get-login-password --region us-east-1 | xargs -I '{}' docker login --username AWS --password '{}'
for version in $VERSION_TAGS
do
  docker tag "$LATEST_TAG" "public.ecr.aws/l7a1d1z4/weco-deploy:$tag"
  docker push "public.ecr.aws/l7a1d1z4/weco-deploy:$tag"
done


