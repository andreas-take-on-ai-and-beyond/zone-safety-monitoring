#!/usr/bin/env bash
# scenario_runner.sh — Interactive demo launcher for zone sensor scenarios
#
# Usage: ./scenario_runner.sh
#
# Presents a numbered menu. Pick a scenario; the script kills any running
# sensor process for that zone, sets SCENARIO=<name>, and relaunches the
# matching sensor_*.py in the background (or foreground if you prefer).
#
# The rest of the pipeline (Kafka → Flink → agent_bridge → dashboard) keeps
# running unchanged — just restart the sensor producer with a new scenario.
#
# Prerequisites: Python environment already active (same one used for sensor_*.py)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="${PYTHON:-python3}"

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'
YEL='\033[0;33m'
GRN='\033[0;32m'
CYN='\033[0;36m'
BLD='\033[1m'
RST='\033[0m'

# ── PID tracking files ────────────────────────────────────────────────────────
# These let us kill the previous instance of each sensor before relaunching.
PID_CNC="${TMPDIR:-/tmp}/sensor_cnc.pid"
PID_ASSEMBLY="${TMPDIR:-/tmp}/sensor_assembly.pid"

_kill_sensor() {
    local pidfile="$1"
    local name="$2"
    if [[ -f "$pidfile" ]]; then
        local pid
        pid=$(<"$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "  ${YEL}⏹  Stopping previous ${name} process (PID ${pid})…${RST}"
            kill "$pid" 2>/dev/null || true
            sleep 1
        fi
        rm -f "$pidfile"
    fi
}

_launch() {
    local script="$1"
    local scenario="$2"
    local pidfile="$3"
    local label="$4"

    echo -e "  ${GRN}▶  Launching ${label} — scenario: ${BLD}${scenario}${RST}"
    SCENARIO="$scenario" PYTHONPATH="$ROOT_DIR/producers:$ROOT_DIR:${PYTHONPATH:-}" $PYTHON "$ROOT_DIR/producers/$script" &
    echo $! > "$pidfile"
    echo -e "  ${CYN}   PID $! → ${pidfile}${RST}"
}

# ── Menu ──────────────────────────────────────────────────────────────────────
print_menu() {
    echo ""
    echo -e "${BLD}╔══════════════════════════════════════════════════════════════╗${RST}"
    echo -e "${BLD}║         Zone Safety Demo — Scenario Selector                ║${RST}"
    echo -e "${BLD}╠══════════════════════════════════════════════════════════════╣${RST}"
    echo -e "${BLD}║  CNC Machining Zone (ENV_SENSOR_ZONE_CNC)                   ║${RST}"
    echo -e "${BLD}╟──────────────────────────────────────────────────────────────╢${RST}"
    echo -e "  ${GRN}1)${RST}  NORMAL               — Healthy shift baseline, no alerts"
    echo -e "  ${RED}2)${RST}  TOOL_BINDING_FIRE    — 🔥 CRITICAL / EHS: Tool dulls → oil ignites"
    echo -e "       ${YEL}Tri-spike: PM2.5 ↑65, CO ↑25 ppm, Temp ↑42°C${RST}"
    echo -e "  ${YEL}3)${RST}  CHIP_BLOWOFF         — 💨 Benign: Brief PM2.5 spike (air gun)"
    echo -e "       ${YEL}PM2.5 spikes to 40 µg/m³ for 5 s; CO + Temp flat — no alarm${RST}"
    echo -e "  ${RED}4)${RST}  COOLANT_LEAK         — 💧 CRITICAL / Mechanics: Pipe bursts"
    echo -e "       ${YEL}Humidity ↑75%, Temp ↑40°C over 60 s; CO flat${RST}"
    echo -e "  ${RED}5)${RST}  BEARING_OVERHEAT     — ⚙️  CRITICAL / Electrical: Dry bearing"
    echo -e "       ${YEL}Temp ↑40°C, Humidity ↓28%, CO slight rise to 8 ppm${RST}"
    echo ""
    echo -e "${BLD}║  Electronics Assembly Zone (ENV_SENSOR_ZONE_ASSEMBLY)       ║${RST}"
    echo -e "${BLD}╟──────────────────────────────────────────────────────────────╢${RST}"
    echo -e "  ${GRN}6)${RST}  NORMAL               — Stable HVAC, CO₂ tracks occupancy"
    echo -e "  ${RED}7)${RST}  FUME_EXTRACTOR_FAILURE — 🔥 WARNING / EHS: Flux fumes build"
    echo -e "       ${YEL}PM2.5 ↑40 µg/m³, CO ↑15 ppm over 2–3 min; Temp flat${RST}"
    echo -e "  ${YEL}8)${RST}  HVAC_HUMIDIFIER_FAILURE — ⚠️  ESD risk: Humidity collapses"
    echo -e "       ${YEL}Humidity 52% → ~22% (fast drop); Flink avg < 30% → Facilities INFO${RST}"
    echo -e "  ${RED}9)${RST}  HVAC_BREAKDOWN       — 🌡️  WARNING / Facilities: CO₂ builds"
    echo -e "       ${YEL}CO₂ 700 → 1 600+ ppm over 5 min; Temp ↑27°C; CO + PM2.5 flat${RST}"
    echo ""
    echo -e "${BLD}╟──────────────────────────────────────────────────────────────╢${RST}"
    echo -e "  ${CYN}0)${RST}  Run BOTH zones in NORMAL mode simultaneously"
    echo -e "  ${RED}q)${RST}  Stop all sensors and quit"
    echo -e "${BLD}╚══════════════════════════════════════════════════════════════╝${RST}"
    echo ""
    printf "Select a scenario [1-9 / 0 / q]: "
}

# ── Main loop ─────────────────────────────────────────────────────────────────
while true; do
    print_menu
    read -r choice

    case "$choice" in
        1)
            _kill_sensor "$PID_CNC" "sensor_cnc.py"
            _launch "sensor_cnc.py" "NORMAL" "$PID_CNC" "CNC Machining"
            ;;
        2)
            _kill_sensor "$PID_CNC" "sensor_cnc.py"
            echo -e "\n  ${RED}${BLD}🔥  TOOL_BINDING_FIRE — oil ignition → EHS CRITICAL${RST}"
            echo -e "  ${YEL}Watch: PM2.5 → 65, CO → 25 ppm, Temp → 42°C — tri-spike fires agent${RST}"
            _launch "sensor_cnc.py" "TOOL_BINDING_FIRE" "$PID_CNC" "CNC Machining"
            ;;
        3)
            _kill_sensor "$PID_CNC" "sensor_cnc.py"
            echo -e "\n  ${YEL}💨  CHIP_BLOWOFF — false-alarm demo (no dispatch fires)${RST}"
            echo -e "  ${YEL}Watch: PM2.5 spikes 1 tick then drops; CO + Temp flat${RST}"
            _launch "sensor_cnc.py" "CHIP_BLOWOFF" "$PID_CNC" "CNC Machining"
            ;;
        4)
            _kill_sensor "$PID_CNC" "sensor_cnc.py"
            echo -e "\n  ${RED}${BLD}💧  COOLANT_LEAK — pipe burst → Mechanics CRITICAL${RST}"
            echo -e "  ${YEL}Watch: Humidity → 75%, Temp → 40°C; CO stays flat${RST}"
            _launch "sensor_cnc.py" "COOLANT_LEAK" "$PID_CNC" "CNC Machining"
            ;;
        5)
            _kill_sensor "$PID_CNC" "sensor_cnc.py"
            echo -e "\n  ${RED}${BLD}⚙️   BEARING_OVERHEAT — dry bearing → Electrical CRITICAL${RST}"
            echo -e "  ${YEL}Watch: Temp → 40°C, Humidity → 28%, CO slight rise to 8 ppm${RST}"
            _launch "sensor_cnc.py" "BEARING_OVERHEAT" "$PID_CNC" "CNC Machining"
            ;;
        6)
            _kill_sensor "$PID_ASSEMBLY" "sensor_assembly.py"
            _launch "sensor_assembly.py" "NORMAL" "$PID_ASSEMBLY" "Electronics Assembly"
            ;;
        7)
            _kill_sensor "$PID_ASSEMBLY" "sensor_assembly.py"
            echo -e "\n  ${RED}${BLD}🔥  FUME_EXTRACTOR_FAILURE — flux fumes → EHS WARNING${RST}"
            echo -e "  ${YEL}Watch: PM2.5 → 40 µg/m³, CO → 15 ppm over 2–3 min${RST}"
            _launch "sensor_assembly.py" "FUME_EXTRACTOR_FAILURE" "$PID_ASSEMBLY" "Electronics Assembly"
            ;;
        8)
            _kill_sensor "$PID_ASSEMBLY" "sensor_assembly.py"
            echo -e "\n  ${YEL}❄️   HVAC_HUMIDIFIER_FAILURE — ESD quality risk → Facilities INFO${RST}"
            echo -e "  ${YEL}Watch: Humidity 52% → ~22% (fast drop); Flink fires on 60-s avg < 30%${RST}"
            echo -e "  ${YEL}Temp + CO + PM2.5 stay flat — agent routes to Facilities (NOT EHS/fire)${RST}"
            _launch "sensor_assembly.py" "HVAC_HUMIDIFIER_FAILURE" "$PID_ASSEMBLY" "Electronics Assembly"
            ;;
        9)
            _kill_sensor "$PID_ASSEMBLY" "sensor_assembly.py"
            echo -e "\n  ${RED}${BLD}🌡️   HVAC_BREAKDOWN — CO₂ builds → Facilities WARNING${RST}"
            echo -e "  ${YEL}Watch: CO₂ → 1 600+ ppm, Temp → 27°C; CO + PM2.5 flat${RST}"
            _launch "sensor_assembly.py" "HVAC_BREAKDOWN" "$PID_ASSEMBLY" "Electronics Assembly"
            ;;
        0)
            _kill_sensor "$PID_CNC" "sensor_cnc.py"
            _kill_sensor "$PID_ASSEMBLY" "sensor_assembly.py"
            echo -e "\n  ${GRN}✅  Starting BOTH zones in NORMAL mode…${RST}"
            _launch "sensor_cnc.py"      "NORMAL" "$PID_CNC"      "CNC Machining"
            _launch "sensor_assembly.py" "NORMAL" "$PID_ASSEMBLY"  "Electronics Assembly"
            ;;
        q|Q|quit|exit)
            echo ""
            echo -e "  ${YEL}⏹  Stopping all sensor processes…${RST}"
            _kill_sensor "$PID_CNC"      "sensor_cnc.py"
            _kill_sensor "$PID_ASSEMBLY" "sensor_assembly.py"
            echo -e "  ${GRN}✅  Done. Kafka, Flink, and the bridge continue running.${RST}"
            echo ""
            exit 0
            ;;
        *)
            echo -e "\n  ${RED}Unknown option '${choice}'. Please enter 1–9, 0, or q.${RST}"
            ;;
    esac

    echo ""
    echo -e "  ${CYN}Sensor running in background. Dashboard at http://localhost:4173${RST}"
    echo -e "  ${CYN}Press Enter to return to the menu, or pick another scenario.${RST}"
    echo ""
    read -r   # wait for Enter before redrawing the menu
done
