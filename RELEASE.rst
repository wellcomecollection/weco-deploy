RELEASE_TYPE: patch

Add some models to describe the weco-deploy config.  These models aren't used yet, but they should make it easier to work on weco-deploy in future.

Note: this release adds a dependency on ``attrs`` and ``cattrs`` (which provide similar typed-models-to-JSON-and-back functionality to case classes and Circe in our Scala apps).