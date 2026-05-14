#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
SKIP_INSTALL="${SKIP_INSTALL:-0}"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

PYTHON="$VENV_DIR/bin/python"
"$PYTHON" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 'Python 3.11+ is required')"

if [[ "$SKIP_INSTALL" != "1" ]]; then
  "$PYTHON" -m pip install -U pip
  "$PYTHON" -m pip install -e ".[server]"
fi

read_env() {
  local key="$1"
  local default_value="${2:-}"
  "$PYTHON" - "$ENV_FILE" "$key" "$default_value" <<'PY'
import os
import sys

path, key, default_value = sys.argv[1], sys.argv[2], sys.argv[3]
value = os.environ.get(key)
if value:
    print(value)
    raise SystemExit

if os.path.exists(path):
    with open(path, encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            candidate_key, candidate_value = line.split("=", 1)
            if candidate_key.strip() == key:
                value = candidate_value.strip()

if value:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    print(value)
else:
    print(default_value)
PY
}

OPENAI_API_KEY_VALUE="$(read_env OPENAI_API_KEY "")"
ENTRY_API_KEY_VALUE="$(read_env ENTRY_API_KEY "")"
ENTRY_HOST_VALUE="$(read_env ENTRY_HOST "0.0.0.0")"
ENTRY_PORT_VALUE="$(read_env ENTRY_PORT "8769")"
UVICORN_WORKERS_VALUE="$(read_env UVICORN_WORKERS "1")"

missing=()
[[ -n "$OPENAI_API_KEY_VALUE" && "$OPENAI_API_KEY_VALUE" != "sk-your-api-key-here" ]] || missing+=("OPENAI_API_KEY")
[[ -n "$ENTRY_API_KEY_VALUE" && "$ENTRY_API_KEY_VALUE" != "replace-with-app-debug-token" ]] || missing+=("ENTRY_API_KEY")

if (( ${#missing[@]} > 0 )); then
  echo "Missing required deployment settings: ${missing[*]}" >&2
  echo "Create .env from .env.example and fill real values, or export them before running this script." >&2
  exit 1
fi

if [[ "$UVICORN_WORKERS_VALUE" != "1" ]]; then
  echo "Warning: UVICORN_WORKERS=$UVICORN_WORKERS_VALUE. Use 1 for App debugging because sessions are in process memory." >&2
fi

export OPENAI_API_KEY="$OPENAI_API_KEY_VALUE"
export ENTRY_API_KEY="$ENTRY_API_KEY_VALUE"
export ENTRY_HOST="$ENTRY_HOST_VALUE"
export ENTRY_PORT="$ENTRY_PORT_VALUE"

echo "Momcozy Agent API: http://${ENTRY_HOST_VALUE}:${ENTRY_PORT_VALUE}"
echo "Health check:      http://${ENTRY_HOST_VALUE}:${ENTRY_PORT_VALUE}/healthz"
echo "App WebSocket:     ws://${ENTRY_HOST_VALUE}:${ENTRY_PORT_VALUE}/api/ag-ui-ws"

exec "$PYTHON" -m uvicorn momcozy_agent.api_app:app \
  --host "$ENTRY_HOST_VALUE" \
  --port "$ENTRY_PORT_VALUE" \
  --workers "$UVICORN_WORKERS_VALUE"

