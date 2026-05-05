# Changelog

All notable changes to this project will be documented in this file.

This project follows a simple date-oriented changelog until formal releases are
introduced.

## Unreleased

- Changed new environments to use `work/` as the mounted project directory.
- Fixed `jovy start` so detached startup does not pass Docker Compose watch.
- Added `jovy --version`, Jupyter init flags, and additional log filtering
  flags.
- Fixed generated Compose files so Jupyter token settings, custom workdirs, and
  Docker Compose watch configuration are honored.
- Added community health documentation.
- Added layered Jupyter notebook image definitions.
