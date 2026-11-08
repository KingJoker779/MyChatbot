#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
	echo "Python 3 is required. Install it from https://www.python.org/downloads/"
	exit 1
fi

exec python3 "$SCRIPT_DIR/project 1.py"
