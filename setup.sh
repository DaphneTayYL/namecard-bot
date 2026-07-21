#!/usr/bin/env bash
# One-time setup. Run once:  bash setup.sh
set -e
cd "$(dirname "$0")"

echo "==> Checking Python…"
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ Python 3 is not installed. Install it from https://www.python.org/downloads/ then re-run this."
  exit 1
fi
python3 --version

echo "==> Creating virtual environment (.venv)…"
python3 -m venv .venv

echo "==> Installing dependencies…"
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt

if [ ! -f .env ]; then
  echo "==> Creating your .env from the template…"
  cp .env.example .env
  echo "    ⚠️  Open .env and fill in your tokens before running (see README steps 3–7)."
else
  echo "==> .env already exists — leaving it alone."
fi

echo ""
echo "✅ Setup done."
echo "   Next: 1) fill in .env   2) add google-creds.json   3) run:  bash run.sh"
