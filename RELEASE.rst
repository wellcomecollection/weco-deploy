RELEASE_TYPE: patch

When deploying services, weco-deploy prints a simpler summary of the changes.
It also skips the ECS deployment if the ECR image tags for a service have not changed.