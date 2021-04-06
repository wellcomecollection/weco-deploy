weco-deploy
===========

A tool for deploying ECS services at the Wellcome Collection.

.. image:: https://badge.buildkite.com/f5f17766a1334f7445548b70ef2c6de1dbb6ba58c6d4ca7cd1.svg
    :target: https://buildkite.com/wellcomecollection/weco-deploy

Installation
------------

For OSX:

Follow this guide to install ``Python 3`` and ``pip``:

https://docs.python-guide.org/starting/install3/osx/

Run: ``pip install weco-deploy``


Setup
-----

Create a ``.wellcome_project`` file in the root of your repo with the
following format:

.. code:: yaml

      my_awesome_project:
        environments:
        - id: prod
          name: Production
        - id: stage
          name: Staging
        # Optional image_repositories block for managing tags in your container repo rather than SSM
        # This is necessary to do automated deploys & will become required in the future
        image_repositories:
        - id: my_service
          namespace: uk.ac.wellcome
          # Optional service block for automated deployments
          # This tag needs to match the value of ECS service tag "deployment:service"
          services:
          - id: ecs_service_tag
        name: My Awesome Project
        role_arn: arn:aws:iam::12345678901:role/platform-ci
        aws_region_name: eu-west-1

To get automated deploy functionality you need to apply the following
tags to ECS services you wish to target in deployment. -
``deployment:service``: must match one of the values given in
``image_repositories.services``. - ``deployment:env``: must match one of
the values given in ``environments``.

Images published to ``ECR`` will be tagged ``env.envname`` where
“envname” is the chosen environment id in the “deploy” step.

In your ECS task definitions you should reference static tags using
those tags, e.g.

::

   760097843905.dkr.ecr.eu-west-1.amazonaws.com/uk.ac.wellcome/my_service:env.prod

Authentication
--------------

The tool assumes you have valid credentials that can be used to assume
the roles specified in configuration.

Process
-------

This tool expects you to follow this process:

-  Publish images to a label in ECR e.g. “latest”.
   Images will also be given a label indicating their git ref.
-  Prepare a release from a label consisting of a set of images at particular git refs
-  Deploy that release into an “environment”
-  Copy images from one tag to another e.g. “latest” -> “env.stage”
-  Use project configuration and ECS Service tags to detect the correct services to redeploy

Publishing images
~~~~~~~~~~~~~~~~~

This step can be run in CI to publish images to ECR and ensure the
correct metadata is available in SSM & ECR

::

   # To publish the local image "my_service:latest" to "uk.ac.wellcome/my_service:latest" in ECR
   weco-deploy publish --image-id my_service

   # To publish the local image "my_service:my_test" to "uk.ac.wellcome/my_service:my_test" in ECR
   weco-deploy publish --image-id my_service --label my_test

Running tests
~~~~~~~~~~~~~~~~~

To run tests locally you can run the following commands:

::

   # Login to ECR using a profile that will give you write access to ECR in the platform account
   aws ecr get-login-password --region eu-west-1 --profile platform | docker login \
      --username AWS \
      --password-stdin \
      760097843905.dkr.ecr.eu-west-1.amazonaws.com

   # Run the docker-compose test override
   docker-compose -f docker-compose.yml -f docker-compose.override.test.yml up

Preparing a release
~~~~~~~~~~~~~~~~~~~

This step will create a record in DynamoDB of the intended deployment
along with when and who prepared the release.

::

   # To prepare a release from latest
   weco-deploy prepare

   # To prepare a release from my_test
   weco-deploy prepare --from-label my_test

Deploying a release
~~~~~~~~~~~~~~~~~~~~

This step will look up a release from dynamo, attempt to apply it to an
environment and record the outcome

::

   # To deploy a release to prod from the last one prep
   weco-deploy deploy --environment-id prod

   # To deploy a particular release to prod
   weco-deploy deploy --environment-id prod --release-id 1234567

Updating a release
~~~~~~~~~~~~~~~~~~~~

This command allowing you to release only specified services. It allows you
to specify a previous release, a comma separated list of services to update
and a label to update them from.

The command creates a new release with the same images as the old release
with only the specified services updated to the given label.

::

   # To update only serviceOne from release 1234567 to ref.abc
   weco-deploy update --release-id 1234567 --service-ids serviceOne --from-label ref.abc

One step prepare/publish
~~~~~~~~~~~~~~~~~~~~~~~~

You can prepare / release in a single step using the release-deploy command

::

   # To deploy a release to prod from the last one prep
   weco-deploy release-deploy --from-label my_test --environment-id prod
