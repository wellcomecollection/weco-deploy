weco-deploy
===========

A tool for deploying ECS services at the Wellcome Collection.

.. image:: https://travis-ci.org/wellcomecollection/weco-deploy.svg?branch=master
    :target: https://travis-ci.org/wellcomecollection/weco-deploy

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
          account_id: '12345678901'
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

This tool expects you to follow this process: - Publish images to a
label in ECR e.g. “latest”, images will also be given a label indicating
their git ref - Prepare a release from a label consisting of a set of
images at particular git refs - Deploy that release into an
“environment” - Copy images from one tag to another e.g. “latest” ->
“env.stage” - Use project configuration and ECS Service tags to detect
the correct services to redeploy

Publishing images
~~~~~~~~~~~~~~~~~

This step can be run in CI to publish images to ECR and ensure the
correct metadata is available in SSM & ECR

::

   # To publish the local image "my_service:latest" to "uk.ac.wellcome/my_service:latest" in ECR
   weco-deploy publish --image-id my_service

   # To publish the local image "my_service:my_test" to "uk.ac.wellcome/my_service:my_test" in ECR
   weco-deploy publish --image-id my_service --label my_test

Preparing a release
~~~~~~~~~~~~~~~~~~~

This step will create a record in DynamoDB of the intended deployment
along with when and who prepared the release.

::

   # To prepare a release from latest
   weco-deploy prepare

   # To prepare a release from my_test
   weco-deploy prepare --from-label my_test

Publishing a release
~~~~~~~~~~~~~~~~~~~~

This step will look up a release from dynamo, attempt to apply it to an
environment and record the outcome

::

   # To deploy a release to prod from the last one prep
   weco-deploy prepare deploy --environment-id prod

   # To deploy a particular release to prod
   weco-deploy prepare deploy --environment-id prod --release-id 1234567
