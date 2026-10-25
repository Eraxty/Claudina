#!/usr/bin/env bash
# starts claudina on this machine: ollama, backend on :8000, website on :3000
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/reactive-ai-gf"
URL="http://localhost:3000"

die() {
  echo "error: $*" >&2
  exit 1
}

port_busy() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
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
command -v node >/dev/null || die "node not found, install Node.js 20.9+ from https://nodejs.org"
node -e 'const [a, b] = process.versions.node.split(".").map(Number); process.exit(a > 20 || (a === 20 && b >= 9) ? 0 : 1)' \
  || die "node $(node --version) is too old, Next.js needs 20.9+"

for port in 3000 8000; do
  if port_busy "$port"; then
    die "port $port is already in use, is claudina already running?"
  fi
done

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

# frontend deps, reinstalled whenever package-lock.json changes
if ! cmp -s "$FRONTEND/package-lock.json" "$FRONTEND/node_modules/.installed" 2>/dev/null; then
  echo "installing website packages..."
  (cd "$FRONTEND" && npm ci)
  cp "$FRONTEND/package-lock.json" "$FRONTEND/node_modules/.installed"
fi

(cd "$BACKEND" && exec venv/bin/python server.py) &
BACKEND_PID=$!
(cd "$FRONTEND" && exec node_modules/.bin/next dev -p 3000) &
FRONTEND_PID=$!

echo "waking her up..."
until port_busy 8000 && port_busy 3000; do
  kill -0 "$BACKEND_PID" 2>/dev/null || die "backend crashed, see the output above"
  kill -0 "$FRONTEND_PID" 2>/dev/null || die "website crashed, see the output above"
  sleep 1
done

echo
echo "claudina is up at $URL  (ctrl+c to stop)"
echo

if command -v xdg-open >/dev/null; then
  xdg-open "$URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null; then
  open "$URL" || true
fi

wait
