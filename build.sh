#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [ ! -x build-venv/bin/python ]; then
  python3 -m venv build-venv
fi

build-venv/bin/pip install pyinstaller ollama python-dotenv groq instagrapi soundfile numpy requests

build-venv/bin/pyinstaller \
  --onefile \
  --name claudina \
  --paths backend \
  --hidden-import insta \
  --hidden-import main \
  --exclude-module torch \
  --exclude-module kokoro \
  --distpath dist \
  --workpath build \
  --specpath build \
  backend/claudina.py

cp backend/.env.example dist/.env.example

echo
echo "done: dist/claudina"
