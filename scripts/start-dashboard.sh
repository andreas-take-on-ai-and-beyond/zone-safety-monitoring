#!/usr/bin/env bash
# start-dashboard.sh — Build and launch the Carbon React dashboard (production)
#
# Prerequisites: Node ≥ 18  +  `npm install express` in project root (once)
# Usage:  ./start-dashboard.sh
#         Then open http://localhost:4173 in your browser.
#
# The dashboard reads dashboard_log.json from the project root every 3 s and
# refreshes automatically — no page reload needed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND="$ROOT_DIR/frontend"

# ── 1. Install / update frontend dependencies ────────────────────────────────
echo "📦  Installing frontend dependencies…"
cd "$FRONTEND" && npm install --silent

# ── 2. Production build ───────────────────────────────────────────────────────
echo "🔨  Building production bundle…"
npm run build

# ── 3. Ensure express is available for the server ────────────────────────────
cd "$ROOT_DIR"
if ! node -e "require('express')" 2>/dev/null; then
  echo "📦  Installing express (server dependency)…"
  npm install --save express --silent
fi

# ── 4. Start the express server ───────────────────────────────────────────────
echo ""
echo "🚀  Zone Safety Dashboard running at http://localhost:4173"
node server.cjs
