#!/usr/bin/env bash
set -euo pipefail
exec "$(dirname "$0")/scripts/unix/test.sh" "$@"