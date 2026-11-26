#!/usr/bin/env bash
# Pinned repo-hygiene check of this checkout against origin/main (#1950); see tools/hygiene/README.md.
# Usage: scripts/hygiene.sh [check] [--base <ref>] [--json]   exit 0 = no new findings, 1 = findings, 2 = error
set -eu
here="$(cd "$(dirname "$0")/.." && pwd)"
[ "${1:-}" = "" ] || [ "${1#-}" != "$1" ] && set -- check "$@"
py=python3; command -v py >/dev/null 2>&1 && py="py -3"
exec $py "$here/tools/hygiene/hygiene.py" "$@"
