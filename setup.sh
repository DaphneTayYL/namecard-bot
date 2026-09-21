#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v python3 >/dev/null 2>&1 || { echo 'Install Python 3.10 or newer, then retry.'; exit 1; }
exec python3 setup.py
