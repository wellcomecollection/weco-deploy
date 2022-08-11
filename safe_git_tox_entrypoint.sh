#!/usr/bin/env sh

# This stops a fatal "unsafe repository" error in Docker inside CI
if [[ -n "$CI" ]]; then
  git config --system --add safe.directory '*'
fi;

tox "$@"
