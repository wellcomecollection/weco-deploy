RELEASE_TYPE: patch

Make the `git config --system --add safe.directory *` command we run to fix "unsafe repository" errors in CI a soft requirement.
It may fail running locally; that's fine.