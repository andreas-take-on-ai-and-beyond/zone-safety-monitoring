#!/bin/zsh
# import-all.sh — Import the zone_safety_native agent and its tools into the active wxO environment.
# Run from the project root.  Dependency order: tools first, agent last.
#
# Usage:
#   orchestrate env activate local   # or your remote env
#   ./import-all.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Zone Safety Native — wxO import ==="
echo "Active environment:"
orchestrate env list | grep "(active)"

echo ""
echo "--- Step 1: Import tools ---"
orchestrate tools import -k python -f "$ROOT_DIR/agents/wxo_native_tools.py"
echo "✅ Tools imported: check_zone_ambient_conditions, get_alert_history, get_prior_dispatches, get_zone_equipment_info, prepare_dispatch_payload"

echo ""
echo "--- Step 2: Import native agent ---"
orchestrate agents import -f "$ROOT_DIR/agents/wxo_native_agent.yaml"
echo "✅ Agent imported: zone_safety_native"

echo ""
echo "--- Step 3: Import local Granite model (optional — skip if already present) ---"
orchestrate models import -f ollama_granite_model.yaml 2>/dev/null && \
  echo "✅ Model imported: virtual-model/ollama/granite4.1-8b" || \
  echo "ℹ️  Model already present or skipped."

echo ""
echo "=== Import complete. Verify with: ==="
echo "  orchestrate agents list"
echo "  orchestrate tools list"
