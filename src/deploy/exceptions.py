class WecoDeployError(Exception):
    pass


class ConfigError(WecoDeployError):
    pass


class EcrError(WecoDeployError):
    pass
