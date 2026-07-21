#!/usr/bin/env bash
# Start the bot. Run:  bash run.sh   (leave the window open; Ctrl-C to stop)
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "❌ No .venv found. Run  bash setup.sh  first."
  exit 1
fi
if [ ! -f .env ]; then
  echo "❌ No .env found. Copy .env.example to .env and fill it in (README steps 3–7)."
  exit 1
fi

exec ./.venv/bin/python namecard_bot.py
