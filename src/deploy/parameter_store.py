from .iam import Iam


class SsmParameterStore:
    def __init__(self, project_id, region_name, role_arn):
        self.project_id = project_id
        self.session = Iam.get_session(
            session_name="ReleaseToolSsmParameterStore",
            role_arn=role_arn,
            region_name=region_name
        )
        self.ssm = self.session.client('ssm')

    @staticmethod
    def _image_to_service_name(image):
        return image.rsplit("/")[-1]

    def get_parameters_by_path(self, *args, **kwargs):
        paginator = self.ssm.get_paginator("get_parameters_by_path")

        for page in paginator.paginate(*args, **kwargs):
            yield from page["Parameters"]

    def get_images(self, label=None):
        ssm_path = self.create_ssm_key(label)

        return self.get_parameters_by_path(
            Path=ssm_path,
            Recursive=True
        )

    def _get_parameter(self, path):
        response = self.ssm.get_parameter(Name=path)
        if response['ResponseMetadata']['HTTPStatusCode'] != 200:
            raise ValueError(
                f"SSM get parameter failed {response['ResponseMetadata']}")
        return response['Parameter']

    def get_services_to_images(self, label):
        ssm_parameters = {d["Name"]: d["Value"]
                          for d in self.get_images(label)}

        return {
            SsmParameterStore._image_to_service_name(key): value for key, value in ssm_parameters.items()
        }

    def get_service_to_image(self, label, service):
        image_path = self.create_ssm_key(label, service)
        parameter = self.ssm.get_parameter(Name=image_path)

        return {
            SsmParameterStore._image_to_service_name(parameter["Parameter"]["Name"]): parameter["Parameter"]["Value"]
        }

    def create_ssm_key(self, label=None, service_id=None):
        # https://github.com/wellcomecollection/platform/tree/master/docs/rfcs/013-release_deployment_tracking#build-artefacts-ssm-parameters
        # Keys are referenced with the following paths:
        #   /{project_id}/images/{label}/{service_id}
        ssm_key_parts = filter(
            lambda part: part is not None,
            ['', self.project_id, 'images', label, service_id])
        ssm_key = "/".join(ssm_key_parts)
        return ssm_key

    def update_ssm(self, service_id, label, image_name, dry_run=False):
        ssm_path = self.create_ssm_key(label, service_id)

        if not dry_run:
            self.ssm.put_parameter(
                Name=ssm_path,
                Description=f"Docker image URL; auto-managed by {__file__}",
                Value=image_name,
                Type="String",
                Overwrite=True
            )

        return {
            'ssm_path': ssm_path,
            'image_name': image_name
        }
