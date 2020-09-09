=========
Changelog
=========

This is a record of all releases of weco-deploy.

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