#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
	echo "Python 3 is required. Install it from https://www.python.org/downloads/"
	exit 1
fi

echo "Downloading the chatbot's own AI engine and model. This needs internet and about 1 GB of storage."
python3 "$SCRIPT_DIR/setup_runtime.py"
exec "$SCRIPT_DIR/run-chatbot.sh"
