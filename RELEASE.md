RELEASE_TYPE: minor

This release changes how weco-deploy verifies deployments.

In particular, it now verifies the image digests rather than the `deployment:label` tag (which is now deprecated and will be removed on future deployments).
See https://github.com/wellcomecollection/weco-deploy/pull/121 for more details.
