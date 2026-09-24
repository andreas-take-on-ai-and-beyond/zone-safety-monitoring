#!/bin/zsh
# run_wxo_bridge.sh — Start the agent bridge in wxO mode.
# Requires WXO_AGENT_ID to be set (UUID from `orchestrate agents list -v`).
#
# Usage:
#   WXO_AGENT_ID=<uuid> ./run_wxo_bridge.sh
#   WXO_DEBUG_DUMP=1 WXO_AGENT_ID=<uuid> ./run_wxo_bridge.sh   # verbose prompt logging

export WXO_BASE_URL="${WXO_BASE_URL:-http://localhost:4321/api/v1}"

# Required: set WXO_AGENT_ID to the UUID shown by `orchestrate agents list -v`
# Copy the UUID for zone_safety_native and pass it as an env var:
#   WXO_AGENT_ID=<your-uuid> ./run_wxo_bridge.sh
if [ -z "${WXO_AGENT_ID:-}" ]; then
  echo "ERROR: WXO_AGENT_ID is not set." >&2
  echo "Run:  orchestrate agents list -v" >&2
  echo "Then: WXO_AGENT_ID=<uuid> ./run_wxo_bridge.sh" >&2
  exit 1
fi
export WXO_AGENT_ID

# Auto-refresh token from credentials.yaml if WXO_BEARER_TOKEN is not already set
if [ -z "${WXO_BEARER_TOKEN:-}" ]; then
  WXO_BEARER_TOKEN="$(python3 - <<'PY'
import yaml, sys
from pathlib import Path
try:
    data = yaml.safe_load((Path.home()/'.cache'/'orchestrate'/'credentials.yaml').read_text())
    print(data['auth']['local']['wxo_mcsp_token'])
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
PY
)"
  export WXO_BEARER_TOKEN
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"
PYTHONPATH="$ROOT_DIR/bridge:$ROOT_DIR:${PYTHONPATH:-}" python3 "$ROOT_DIR/bridge/agent_bridge.py"
