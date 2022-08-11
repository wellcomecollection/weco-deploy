=========
Changelog
=========

This is a record of all releases of weco-deploy.

-------------------
5.6.41 - 2022-08-11
-------------------

Fixes to deployment mechanisms

-------------------
5.6.40 - 2022-08-11
-------------------

Fix the content-type in `setup.py` to fix publishing to PyPI.

-------------------
5.6.39 - 2022-04-25
-------------------

A no-op change to try to trigger a deployment.

-------------------
5.6.38 - 2022-04-21
-------------------

* Add "confirm-deploy" command
* Ensure that deployment checks only look at things that changed

-------------------
5.6.37 - 2021-05-18
-------------------

If there is nothing to release, don't cut a release!

-------------------
5.6.36 - 2021-05-17
-------------------

Tolerate missing images for some services within a project in a release.

-------------------
5.6.35 - 2021-04-29
-------------------

Fix for where role_arn is unset and verbose is set on causing boom

-------------------
5.6.34 - 2021-04-28
-------------------

Fix a bug where an unavailable service for an env causes a deployment to fail.

-------------------
5.6.33 - 2021-04-28
-------------------

Add a check on missing images when preparing releases and improve known error display.

-------------------
5.6.32 - 2021-04-21
-------------------

Add a few more tests around the ECR-related code, and fix a deploy-related bug.

-------------------
5.6.31 - 2021-04-15
-------------------

Fix a couple of issues introduced in recent refactoring.

-------------------
5.6.30 - 2021-04-12
-------------------

Fix a bug introduced in the recent refactoring work.

-------------------
5.6.29 - 2021-04-07
-------------------

More internal refactoring that should have no user-visible effect.

-------------------
5.6.28 - 2021-04-07
-------------------

More internal refactoring that should have no user-visible effect.

-------------------
5.6.27 - 2021-04-07
-------------------

More internal refactoring that should have no user-visible effect.

-------------------
5.6.26 - 2021-04-06
-------------------

This does some refactoring to use our new models for config parsing and validation.  There should be no user-visible effect.

-------------------
5.6.25 - 2021-04-06
-------------------

Simplify the code slightly by removing namespace overrides, which we never use in practice.  We always use the default namespace ``uk.ac.wellcome``.

-------------------
5.6.24 - 2021-04-06
-------------------

Fix wait-for-deploy by restoring cache-busting ability to ECS service fetcher

-------------------
5.6.23 - 2021-04-06
-------------------

Simplify the code slightly by removing account/registry ID overrides, which we never use in practice.  We always use the default ECR registry.

-------------------
5.6.22 - 2021-04-06
-------------------

Add some models to describe the weco-deploy config.  These models aren't used yet, but they should make it easier to work on weco-deploy in future.

Note: this release adds a dependency on ``attrs`` and ``cattrs`` (which provide similar typed-models-to-JSON-and-back functionality to case classes and Circe in our Scala apps).

-------------------
5.6.21 - 2021-04-06
-------------------

Simplify the code slightly by removing per-image repository and per-service overrides, which we never use in practice.

-------------------
5.6.20 - 2021-03-31
-------------------

More refactoring towards support for ECR Public.

-------------------
5.6.19 - 2021-03-31
-------------------

Fixes running prepare when there are no releases

-------------------
5.6.18 - 2021-03-30
-------------------

This does some internal refactoring to prepare for supporting ECR Public repositories in a future release.

-------------------
5.6.17 - 2021-03-30
-------------------

No-op change to get our CI working again with python-cryptography and Rust.

-------------------
5.6.16 - 2021-01-08
-------------------

Fix issue with deploy_release step erroring

-------------------
5.6.15 - 2021-01-08
-------------------

Bump for release, fix docker script

-------------------
5.6.14 - 2021-01-08
-------------------

Bump for release, fix docker script

-------------------
5.6.13 - 2021-01-08
-------------------

Bump to attempt to fix docker packaging incorrect version

-------------------
5.6.12 - 2021-01-05
-------------------

Only log task/service info when waiting for deploy if the verbose flag is set

-------------------
5.6.11 - 2020-11-30
-------------------

Warn when weco-deploy is not the latest version.

-------------------
5.6.10 - 2020-11-25
-------------------

Fix undefined variable when task is not yet running

------------------
5.6.9 - 2020-11-25
------------------

Fix invalid cache that was causing deploy waiting to return early

------------------
5.6.8 - 2020-11-20
------------------

Fix inability to prepare release, and missing namespace on image_repositories

------------------
5.6.7 - 2020-11-18
------------------

Fixes to ECR publishing

------------------
5.6.6 - 2020-11-18
------------------

weco-deploy is now published to our private ECR registry as well as Docker Hub.

------------------
5.6.5 - 2020-11-06
------------------

Internal refactoring to improve testing.  This should have no user-visible effect.

------------------
5.6.4 - 2020-11-05
------------------

Internal refactoring to improve testing, plus fixing bugs in the ``show-deployments`` command.

------------------
5.6.3 - 2020-11-05
------------------

Internal refactoring to improve testing.  This should have no user-visible effect.

------------------
5.6.2 - 2020-11-04
------------------

Internal refactoring to improve testing.  This should have no user-visible effect.

------------------
5.6.1 - 2020-11-04
------------------

Internal refactoring to improve testing.  This should have no user-visible effect.

------------------
5.6.0 - 2020-11-04
------------------

Adds an --environment-id filter to show-deployments command. This allows a better view on deployments when looking for example for the last good prod deploy.

-------------------
5.5.13 - 2020-11-04
-------------------

Internal refactoring to improve testing.  This should have no user-visible effect.

-------------------
5.5.12 - 2020-11-03
-------------------

Internal refactoring.  This should have no user-visible effect.

-------------------
5.5.11 - 2020-11-03
-------------------

Internal refactoring to remove unused code.  This should have no user-visible effect.

-------------------
5.5.10 - 2020-11-03
-------------------

Internal refactoring to remove unused code.  This should have no user-visible effect.

------------------
5.5.9 - 2020-11-03
------------------

Internal refactoring to remove unused code.  This should have no user-visible effect.

------------------
5.5.8 - 2020-11-03
------------------

Internal refactoring.  This should have no user-visible effect.

------------------
5.5.7 - 2020-10-23
------------------

weco-deploy now gives more detailed explanations of why a deployment hasn't completed.

------------------
5.5.6 - 2020-10-23
------------------

Handle the case asked to describe an image that does not exist gracefully.

This fixes an issue with the update command that would fail when the label requested was not available for all services in a project, even though a subset were being updated.

------------------
5.5.5 - 2020-10-23
------------------

Internal refactoring.  This should have no user-visible effect.

------------------
5.5.4 - 2020-10-23
------------------

Make weco-deploy slightly faster when looking up Git commits.

------------------
5.5.3 - 2020-10-23
------------------

Fix a bug where weco-deploy would erroneously report that region config was missing, when actually the role ARN was missing.

------------------
5.5.2 - 2020-10-23
------------------

Fix check for complete deployment

------------------
5.5.1 - 2020-10-23
------------------

Speed up loading the table "ECS services discovered" when running the ``deploy`` command.

------------------
5.5.0 - 2020-10-22
------------------

Makes waiting for a deployment more verbose by displaying time waited, along with wait time expectation, and totals after deployment.

------------------
5.4.4 - 2020-10-20
------------------

Show the defaults for the ``--confirmation-wait-for`` and ``--confirmation-interval`` flags.

------------------
5.4.3 - 2020-10-15
------------------

Removing some unused code.  This should have no user-visible effect.

------------------
5.4.2 - 2020-10-14
------------------

Fixes some errors when tasks are not available or when moving from an unmanaged to a managed state

------------------
5.4.1 - 2020-10-14
------------------

Adds `_confirm_deploy` to the `release_deploy` cli command.

------------------
5.4.0 - 2020-10-14
------------------

Adds `_confirm_deploy` to the deploy step, ensuring that the `deployment:label` tag on a service matches the `deployment:label` tag on the tasks within that service.

------------------
5.3.3 - 2020-10-14
------------------

Logs written during a deployment are saved to ``~/.local/share/weco-deploy``, not ``~/local/share/weco-deploy``.

------------------
5.3.2 - 2020-10-14
------------------

Bump for release

------------------
5.3.1 - 2020-10-12
------------------

Bump for release

------------------
5.3.0 - 2020-10-09
------------------

Allow getting more than 10 deployments with the ``show-deployments`` command.

Get more deployments by passing ``--limit=LIMIT``, e.g. ``--limit=25``.

------------------
5.2.3 - 2020-10-09
------------------

Fix an unexpected error that would be thrown if you passed `--project-id` with an unrecognised project ID.

------------------
5.2.2 - 2020-10-09
------------------

When running the ``show-deployments`` command, you always get a consistent number of deployments (the most recent 10) and deployments are sorted by deployment date.

------------------
5.2.1 - 2020-10-08
------------------

Fix a bug that meant the prepare-deploy command would always throw an exception.

------------------
5.2.0 - 2020-09-30
------------------

Adds a new update command, allowing specific services to be updated from a previous release.

------------------
5.1.1 - 2020-09-24
------------------

Fix an issue with the indentation of output when running with ``--verbose``.

------------------
5.1.0 - 2020-09-24
------------------

When a deployment occurs, ECS services will be tagged with the release id at key "deployment:label".

This provides a way to identify the release a service should be trying to enact (and by looking up that relationship identify which image is associated with which task).

-------------------
5.0.18 - 2020-09-18
-------------------

Adds openssh to the Dockerfile (required by git in some environments).

-------------------
5.0.17 - 2020-09-17
-------------------

Deal with no previous releases being available.

-------------------
5.0.16 - 2020-09-17
-------------------

When deploying services, weco-deploy prints a simpler summary of the changes.
It also skips the ECS deployment if the ECR image tags for a service have not changed.

-------------------
5.0.15 - 2020-09-17
-------------------

Make it easier to read the list of ECS services discovered when deploying new images.

-------------------
5.0.14 - 2020-09-17
-------------------

Fix the printing of coloured tables in the weco-deploy output.

-------------------
5.0.13 - 2020-09-10
-------------------

Fix bug deploying where images do not have a service

-------------------
5.0.12 - 2020-09-09
-------------------

bump for release

-------------------
5.0.11 - 2020-09-09
-------------------

Bump for release

-------------------
5.0.10 - 2020-09-09
-------------------

Bump for release

------------------
5.0.9 - 2020-09-09
------------------

Bump for release

------------------
5.0.8 - 2020-09-09
------------------

Bump for release

------------------
5.0.7 - 2020-09-09
------------------

bump for release

------------------
5.0.6 - 2020-09-09
------------------

bump for new ci

------------------
5.0.5 - 2020-09-09
------------------

Bump for new CI

------------------
5.0.4 - 2020-09-09
------------------

Bump for new CI

------------------
5.0.3 - 2020-08-05
------------------

Fix a bug that caused the `release-deploy` command to fail.

------------------
5.0.2 - 2020-07-23
------------------

Nicer colours & handle no matching services in deploy step

------------------
5.0.1 - 2020-07-23
------------------

Some internal refactoring that should have no user visible effect.

------------------
5.0.0 - 2020-07-23
------------------

Better handling of defaults to reduce repetition, services have their own config to allow deployment into differing accounts/regions.

------------------
4.1.6 - 2020-07-21
------------------

Modify the output of the ``deploy`` command to show a table of ECS services discovered.

------------------
4.1.5 - 2020-07-21
------------------

Fix a bug in the ``prepare`` command that would throw a subprocess.CalledProcessError if your release included a Git commit that you didn't have locally.

------------------
4.1.4 - 2020-07-21
------------------

When running the ``show-images`` command, print a table rather than a list.

------------------
4.1.3 - 2020-07-21
------------------

When running the ``prepare`` command, show a table of services, the Git commit of the previous and new release, and the commit message associated with the new images.

------------------
4.1.2 - 2020-07-20
------------------

Fix a bug in the ``show-deployments`` command.

------------------
4.1.1 - 2020-07-20
------------------

Ensure services are not deployed multiple times where a service is targeted multiple times in a deployment

------------------
4.1.0 - 2020-07-18
------------------

Updates readme and adds a missing namespace param to the prepare command

------------------
4.0.0 - 2020-07-17
------------------

Makes the code a bit nicer, publish takes --image-id rather than --service-id

------------------
3.3.2 - 2020-07-17
------------------

Allow parsing yaml as config, fix some bugs

------------------
3.3.1 - 2020-07-16
------------------

Try to fix ECR login again.

------------------
3.3.0 - 2020-07-16
------------------

Fix an issue where ecr login failed because of IAM auth problems.

------------------
3.2.0 - 2020-07-16
------------------

Auto-detect ECS services and ask to deploy if configuration is available.

------------------
3.1.0 - 2020-07-14
------------------

If provided images described in .wellcome-project will be used instead of referring to SSM.

------------------
3.0.0 - 2020-07-13
------------------

Adds tagging ECR images wiht enviroment

------------------
2.0.0 - 2020-07-10
------------------

Clean up a bit, simplify piublish command and fix a bug where full repo was not written to SSM.

------------------
1.0.0 - 2020-07-10
------------------

Incorporate release tooling commands

-------------------
0.19.0 - 2020-07-09
-------------------

Bump for release

-------------------
0.18.0 - 2020-07-09
-------------------

Bump for release

-------------------
0.17.0 - 2020-07-09
-------------------

Bump for release

-------------------
0.16.0 - 2020-07-09
-------------------

Bump for release

-------------------
0.15.0 - 2020-07-08
-------------------

Bump for release

-------------------
0.14.0 - 2020-07-08
-------------------

Fix dockerfile

-------------------
0.13.0 - 2020-07-08
-------------------

Add build step for docker hub

-------------------
0.12.0 - 2020-07-08
-------------------

Adds image publishing logic

-------------------
0.11.0 - 2020-07-08
-------------------

Bump for release

-------------------
0.10.0 - 2020-07-08
-------------------

Bump for release

------------------
0.9.0 - 2020-07-08
------------------

Bump for release

------------------
0.8.0 - 2020-07-08
------------------

Bump for release

------------------
0.7.0 - 2020-07-08
------------------

Bump for release.

------------------
0.6.0 - 2020-07-08
------------------

Bump for release.

------------------
0.5.0 - 2020-07-08
------------------

Bump for release.

------------------
0.4.0 - 2020-07-07
------------------

Bump for release

------------------
0.3.0 - 2020-07-07
------------------

Bump for release

------------------
0.2.0 - 2020-07-07
------------------

Bump for release.

------------------
0.0.1 - 2020-07-07
------------------

Initial import.