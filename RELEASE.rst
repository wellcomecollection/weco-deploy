RELEASE_TYPE: patch

Fix a bug in the ``prepare`` command that would throw a subprocess.CalledProcessError if your release included a Git commit that you didn't have locally.
