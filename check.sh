#!/usr/bin/env bash
set -euo pipefail

"$(dirname "$0")/lint.sh"
"$(dirname "$0")/test.sh" "$@"
