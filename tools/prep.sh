#!/bin/sh
# Compatibility entry: the real prep is tools/prep.py (works on Windows too). usage: tools/prep.sh <session> [people]
PYBIN="$(dirname "$0")/../.venv/bin/python"
[ -x "$PYBIN" ] || { echo "run ./setup.sh first"; exit 1; }
exec "$PYBIN" "$(dirname "$0")/prep.py" "$@"
