import functools
import subprocess

from .commands import cmd


def _fix_dubious_ownership():
    # This stops a fatal "unsafe repository" error in Docker inside CI
    return subprocess.check_call(['git', 'config', '--system', '--add', 'safe.directory', '*'])


@functools.lru_cache()
def log(commit_id, run_fetch=True):
    """
    Returns a one-line log for a given commit ID.
    """
    _fix_dubious_ownership()

    try:
        # %s = subject, the first line of the commit
        # See https://git-scm.com/docs/pretty-formats
        show_cmd = ["git", "show", "-s", "--format=%s", commit_id]
        return subprocess.check_output(show_cmd).decode("utf8").strip()

    except subprocess.CalledProcessError:
        # If we couldn't find the commit, run 'git fetch' and see if it's
        # available in the remote state.  If we still can't find it after that,
        # give up and return an empty string.
        if run_fetch:
            cmd("git", "fetch", "origin")
            log(commit_id, run_fetch=False)
        else:
            return ""


def repo_root():
    """
    Returns the path to the root of the repository.
    """
    # This stops a fatal "unsafe repository" error in Docker inside CI
    _fix_dubious_ownership()

    return cmd("git", "rev-parse", "--show-toplevel")
