import functools

from .commands import cmd


@functools.lru_cache()
def log(commit_id):
    """
    Returns a one-line log for a given commit ID.
    """
    return cmd("git", "show", "-s", "--format=%B", commit_id)
