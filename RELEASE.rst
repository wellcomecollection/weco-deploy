RELEASE_TYPE: patch

Handle the case asked to describe an image that does not exist gracefully.

This fixes an issue with the update command that would fail when the label requested was not available for all services in a project, even though a subset were being updated.
