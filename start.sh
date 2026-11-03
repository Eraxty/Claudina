#!/usr/bin/env bash
# starts claudina on this machine: ollama, then a chat with her in this terminal
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"

die() {
  echo "error: $*" >&2
  exit 1
}

# kokoro (her voice) only installs on python 3.10 - 3.12
find_python() {
  for py in python3.12 python3.11 python3.10 python3; do
    if command -v "$py" >/dev/null && "$py" -c 'import sys; sys.exit(not (3, 10) <= sys.version_info[:2] <= (3, 12))'; then
      echo "$py"
      return
    fi
  done
  return 1
}

cleanup() {
  trap - EXIT INT TERM
  kill $(jobs -p) 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

command -v ollama >/dev/null || die "ollama not found, install it from https://ollama.com"

# ollama: start it ourselves if it isn't already running
if ! ollama list >/dev/null 2>&1; then
  echo "starting ollama..."
  ollama serve >/dev/null 2>&1 &
  for _ in $(seq 30); do
    ollama list >/dev/null 2>&1 && break
    sleep 1
  done
  ollama list >/dev/null 2>&1 || die "ollama didn't start, try running 'ollama serve' yourself"
fi

MODEL="${OLLAMA_MODEL:-}"
if [ -z "$MODEL" ] && [ -f "$BACKEND/.env" ]; then
  MODEL="$(sed -n 's/^OLLAMA_MODEL=//p' "$BACKEND/.env" | tail -n 1 | tr -d "\"'")"
fi
MODEL="${MODEL:-gemma3:4b}"
export OLLAMA_MODEL="$MODEL"

if ! ollama show "$MODEL" >/dev/null 2>&1; then
  echo "downloading $MODEL, first run only..."
  ollama pull "$MODEL"
fi

# backend deps, reinstalled whenever requirements.txt changes
if ! cmp -s "$BACKEND/requirements.txt" "$BACKEND/venv/.installed" 2>/dev/null; then
  echo "installing backend packages, this takes a while the first time..."
  if [ ! -x "$BACKEND/venv/bin/python" ]; then
    PY="$(find_python)" || die "her voice needs python 3.10, 3.11 or 3.12, install one of those"
    "$PY" -m venv "$BACKEND/venv"
  fi
  "$BACKEND/venv/bin/pip" install -r "$BACKEND/requirements.txt"
  cp "$BACKEND/requirements.txt" "$BACKEND/venv/.installed"
fi

INSTA=""
if [ -f "$BACKEND/.env" ]; then
  INSTA="$(sed -n 's/^INSTA_USERNAME=//p' "$BACKEND/.env" | tail -n 1 | tr -d "\"'")"
fi

cd "$BACKEND"

# instagram if her account is set up in .env, otherwise chat right here
if [ -n "$INSTA" ]; then
  echo
  echo "claudina is up on instagram as @$INSTA  (ctrl+c to stop)"
  echo
  venv/bin/python insta.py
else
  echo
  echo "claudina is up, say hi  (ctrl+d to stop)"
  echo
  venv/bin/python main.py
fi
