# weco-deploy

[![Build status](https://badge.buildkite.com/f5f17766a1334f7445548b70ef2c6de1dbb6ba58c6d4ca7cd1.svg)](https://buildkite.com/wellcomecollection/deployment-cli-weco-deploy)

weco-deploy helps us deploy applications as Docker images within Amazon ECS.

This tool only makes sense in the context of how we tag and deploy images, so this README explains our broad approach and how we use weco-deploy.



## How we tag our Docker images

We package applications as Docker images.
Images are automatically pushed on every merge to a main branch, and pushed to an ECR repository.

Within our ECR repository, we have three types of tag.
Here's a list of images, to serve as an example:

<img src="./docs/ecr_tags.png" alt="A screenshot of the ECR console, showing a repo with five images.">

Here's how we tag images:

-   Every image has a tag starting `ref`; this is the Git commit has that was used to build a given image.
    This helps us match an image to its source code.

-   The `latest` tag points to the last image that was pushed to this repository.
    It helps us know what the newest version of our code is.

    This tag is updated by our CI/CD pipeline.

-   The `env` tags point to the image being used in a particular environment.
    For example, we can see here there are images with an `env.stage` and an `env.prod` tag – these are the images used in our staging and prod environment, respectively.

    These are floating tags set by weco-deploy.



## How we use tags to deploy images

Within our ECS task definitions, we point to an `env` tag as the Docker image to use.

```
{
  "containerDefinitions": [
    {
      "image": "{ECR repository prefix}/our_app:env.stage",
      ...
    }
  ],
  ...
}
```

weco-deploy gives us tools for updating these floating `env` tags.
This is easiest to explain with some example scenarios:

*   Example #1: We've pushed some new code, and we want to deploy it to our staging environment.

    First our CI/CD pipeline builds new Docker images, publishes them to an ECR repository, and tags them with `latest`.
    Then we ask weco-deploy to update the `env.stage` tag to point to the images that are currently tagged `latest`.
    Finally, weco-deploy tells ECS to redeploy any services using that tag, which causes them to pull the new Docker image.

*   Example #2: We've tested the code in staging, we're satisfied it works, and we want to deploy it to production.

    First we ask weco-deploy to update the `env.prod` tag to point to the images that are currently tagged `env.stage`.
    Then, weco-deploy tells ECS to redeploy any services using that tag, which causes them to pull the new Docker image.

weco-deploy also tracks all the deployments, so we can see what code was deployed when.



## Terminology

These are the terms which are used by weco-deploy, which have a fairly specific meaning in this context:

<dl>
  <dt>project</dt>
  <dd>
    A collection of images/services that are deployed together.
    Different projects are managed independently, e.g. we can deploy new images to the catalogue API without affecting the storage service.
  </dd>

  <dt>release</dt>
  <dd>
    A set of specific versions of Docker images that can be deployed together.
    e.g. The set of images `bag_verifier:ref.123`, `bag_replicator:ref.456` and `bag_unpacker:ref.789`.
  </dd>

  <dt>deployment</dt>
  <dd>
    The act of applying a release to an environment.
    i.e. telling ECS to use a particular set of images.<br/><br/>
    A release is just an abstract concept; a deployment is making it concrete by deploying the images.
    Note that one release might be used in multiple deployments: for example, deploying a release to a staging environment and then a production environment.
  </dd>

  <dt>.wellcome_project file</dt>
  <dd>
    A YAML file that is used to configure weco-deploy: in particular, listing each project, the Docker images it contains, and what ECS services need to be redeployed when the image tags are updated.
    The easiest way to understand is to <a href="https://github.com/wellcomecollection/catalogue-pipeline/blob/main/.wellcome_project">look at an example</a>.
  </dd>
</dl>



## Installation

weco-deploy is published as a package to PyPI, so you can install it with pip:

```console
$ pip3 install weco-deploy
```



## Usage

Most of our use of weco-deploy is automated in Buildkite, so manual use is rare.

The most useful subcommands are:

```
$ # create a new release, but don't deploy it
$ weco-deploy prepare

$ # deploy a previously created release
$ weco-deploy deploy

$ # create a new release and deploy it straight to ECS
$ weco-deploy release-deploy
```

You can select a project/label using command-line flags, or if not the tool will prompt you for the required inputs.
