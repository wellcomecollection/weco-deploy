import click
from distutils.version import LooseVersion
import json
import urllib

from .version import __version__ as current_version_str

current_version = LooseVersion(current_version_str)


def warn_if_not_latest_version():
    with urllib.request.urlopen("https://pypi.org/pypi/weco-deploy/json") as response:
        try:
            response_body = response.read().decode('utf-8')
            data = json.loads(response_body)
            release_versions = data["releases"].keys()
            latest_version = max([LooseVersion(v) for v in release_versions])
            latest_version_str = latest_version.vstring
            if current_version < latest_version:
                click.echo(click.style(f"You are using weco-deploy version {current_version_str}. "
                                       f"However, version {latest_version_str} is available.", fg="red"))
                click.echo(click.style("You should consider upgrading via the 'pip install --upgrade weco-deploy' "
                                       "command.", fg="yellow"))
        except urllib.error.URLError:
            # This is likely due to a network error, so ignore it
            pass
        except Exception as e:
            click.echo(click.style("Error when checking for latest version:", fg="red"))
            click.echo(e)
