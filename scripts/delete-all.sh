#!/bin/zsh
# delete-all.sh — Remove the zone_safety_native agent and its tools from the active wxO environment.
# Reverse dependency order: agent first, tools last.
#
# Usage:
#   orchestrate env activate local   # or your remote env
#   ./delete-all.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Zone Safety Native — wxO delete ==="
echo "Active environment:"
orchestrate env list | grep "(active)"

echo ""
echo "--- Step 1: Delete native agent ---"
orchestrate agents delete -n zone_safety_native 2>/dev/null && \
  echo "✅ Agent deleted: zone_safety_native" || \
  echo "ℹ️  Agent not found or already deleted."

echo ""
echo "--- Step 2: Delete tools ---"
for tool in check_zone_ambient_conditions get_alert_history get_prior_dispatches get_zone_equipment_info prepare_dispatch_payload; do
  orchestrate tools delete -n "$tool" 2>/dev/null && \
    echo "✅ Tool deleted: $tool" || \
    echo "ℹ️  Tool $tool not found or already deleted."
done

echo ""
echo "=== Delete complete. ==="
