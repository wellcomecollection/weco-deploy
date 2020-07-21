import functools
import subprocess

from .commands import cmd


@functools.lru_cache()
def log(commit_id):
    """
    Returns a one-line log for a given commit ID.
    """
    try:
        cmd("git", "fetch", "origin")

        # %s = subject, the first line of the commit
        # See https://git-scm.com/docs/pretty-formats
        return cmd("git", "show", "-s", "--format=%s", commit_id)
    except subprocess.CalledProcessError:
        return ""
