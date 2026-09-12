#!/usr/bin/env bash
# Unix wrapper around run.py
set -e
cd "$(dirname "$0")"
exec python3 run.py "$@"
