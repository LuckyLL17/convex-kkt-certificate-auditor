#!/bin/sh
set -eu
cp "$(dirname "$0")/src/verify.py" /app/src/verify.py
chmod 755 /app/src/verify.py
