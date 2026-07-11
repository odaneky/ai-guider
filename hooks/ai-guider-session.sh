#!/bin/bash
# AI Guider sessionStart bootstrap
set -euo pipefail
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="${AI_GUIDER_PYTHONPATH:-${HOOK_DIR}/../src}:${PYTHONPATH:-}"
# Prefer project venv if present
if [[ -x "${HOOK_DIR}/../.venv/bin/python" ]]; then
  PY="${HOOK_DIR}/../.venv/bin/python"
elif [[ -x "${HOME}/ai-guider/.venv/bin/python" ]]; then
  PY="${HOME}/ai-guider/.venv/bin/python"
  export PYTHONPATH="${HOME}/ai-guider/src:${PYTHONPATH:-}"
else
  PY="python3"
fi
exec "$PY" "${HOOK_DIR}/ai_guider_hook.py" sessionStart
