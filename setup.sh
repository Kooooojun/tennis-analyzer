#!/bin/sh
# Compatibility entry: the real setup is setup.py, which finds Python 3.11/3.12 itself. usage: ./setup.sh [--cuda]
exec python3 "$(dirname "$0")/setup.py" "$@"
