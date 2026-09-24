import json
import os
import re
from datetime import datetime

from ibm_watsonx_orchestrate.agent_builder.tools import tool

# ---------------------------------------------------------------------------
# Zone baselines — single source of truth for zone-aware threshold logic in
# check_zone_ambient_conditions and get_alert_history.
# ---------------------------------------------------------------------------
_ZONE_BASELINES = {
    "ENV_SENSOR_ZONE_CNC": {
        "zone_type":            "CNC Machining",
        "temp_baseline_c":      26.0,
        "temp_normal_range":    "24–28 °C",
        "temp_alert_c":         38.0,
        "hum_baseline_pct":     45.0,
        "hum_normal_range":     "40–50 %",
        "co_baseline_ppm":       4.0,
        "co_normal_range":       "2–6 ppm",
        "pm25_baseline_ugm3":   15.0,
        "pm25_normal_range":    "10–20 µg/m³",
        "co2_baseline_ppm":    650.0,
        "co2_normal_range":     "600–750 ppm",
        "risk_notes": (
            "Zone contains one machine: Mazak VARIAXIS i-500 (5-axis mill-turn). "
            "Coolant mist and metal dust are permanently present at baseline — "
            "PM2.5 sawtooth during part swaps is expected and not alarming on its own. "
            "CO trace from tramp oil and hydraulic heating is normal up to 6 ppm. "
            "When PM2.5, CO, and temperature all rise simultaneously, this indicates "
            "a cutting-fluid ignition or oil-mist combustion inside the machine enclosure ENCL-CNC-01. "
            "When humidity surges above 60 % with flat CO, this indicates a coolant pipe failure "
            "(high-pressure pump PUMP-TSC-01 or flood pump PUMP-FLOOD-01 has lost containment). "
            "When temperature rises and humidity falls below 35 % with CO only slightly elevated, "
            "this indicates dry-friction heat — likely spindle bearings BRG-SPINDLE-U/BRG-SPINDLE-L "
            "or trunnion bearings BRG-TRUNNION-L/BRG-TRUNNION-R running dry."
        ),
    },
    "ENV_SENSOR_ZONE_ASSEMBLY": {
        "zone_type":            "Electronics Assembly",
        "temp_baseline_c":      21.0,
        "temp_normal_range":    "20.5–21.5 °C",
        "temp_alert_c":         26.0,
        "hum_baseline_pct":     52.0,
        "hum_normal_range":     "50–55 % (ESD-safe window; below 30 % triggers ESD risk)",
        "co_baseline_ppm":       2.0,
        "co_normal_range":       "1.5–3 ppm",
        "pm25_baseline_ugm3":    5.0,
        "pm25_normal_range":    "3–8 µg/m³ (near-cleanroom with fume extractors running)",
        "co2_baseline_ppm":    700.0,
        "co2_normal_range":     "500–900 ppm (occupancy-dependent)",
        "risk_notes": (
            "Zone contains one SMT line: DEK Horizon 03i → Yamaha YSM20R → Heller 1809 MK5. "
            "Temperature above 26 °C is a process risk per IPC-A-610 soldering environment specification. "
            "Humidity below 30 % causes ESD risk — ESD flooring ESD-FLOOR-ZONE2 loses conductivity "
            "and IC assembly on the YSM20R must halt immediately. "
            "CO₂ above 1 500 ppm with rising temperature and flat CO/PM2.5 indicates HVAC air supply "
            "failure at AHU-ASSEMBLY-01 — worker cognitive performance measurably impaired above 1 500 ppm. "
            "PM2.5 rises with CO when fume extraction fails (reflow exhaust blower BLOWER-REFLOW-01 "
            "or paste printer extractor FUME-EXT-PRINTER has lost its duct path); "
            "temperature stays flat in this case — distinguishing it from a zone thermal event. "
            "Humidity collapses in isolation (all other signals flat) when humidifier HUM-ASSEMBLY-01 fails."
        ),
    },
}

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
ALERT_HISTORY_FILE = os.getenv(
    "ALERT_HISTORY_FILE",
    os.path.join(_ROOT, "alert_history.json"),
)
SENSOR_LOG_FILE = os.getenv(
    "SENSOR_LOG_FILE",
    os.path.join(_ROOT, "sensor_log.json"),
)


# ---------------------------------------------------------------------------
# Tool 1 — check_zone_ambient_conditions (zone-aware, pressure removed)
# ---------------------------------------------------------------------------

@tool()
def check_zone_ambient_conditions(
    sensor_id: str,
    temperature_c: float,
    humidity_pct: float,
    co2_ppm: float,
    co_ppm: float,
    pm25_ugm3: float,
    zone: str,
) -> str:
    """Checks the current environmental conditions against zone-specific baselines.

    Args:
        sensor_id (str): Sensor identifier — used to apply the correct zone baselines.
        temperature_c (float): Current measured temperature in degrees Celsius.
        humidity_pct (float): Current measured relative humidity percentage.
        co2_ppm (float): Current measured carbon dioxide concentration in ppm.
        co_ppm (float): Current measured carbon monoxide concentration in ppm.
        pm25_ugm3 (float): Current measured PM2.5 concentration in micrograms per cubic meter.
        zone (str): Human-readable zone name for the alert.
    Returns:
        str: A structured environmental report calibrated to the zone's normal operating ranges.
    """
    b = _ZONE_BASELINES.get(sensor_id, _ZONE_BASELINES["ENV_SENSOR_ZONE_CNC"])
    temp_alert  = b["temp_alert_c"]
    temp_base   = b["temp_baseline_c"]
    hum_base    = b["hum_baseline_pct"]
    co_base     = b["co_baseline_ppm"]
    pm25_base   = b["pm25_baseline_ugm3"]
    co2_base    = b["co2_baseline_ppm"]

    # ── Temperature (zone-aware threshold) ───────────────────────────────────
    temp_delta = temperature_c - temp_base
    if temperature_c > temp_alert + 2.0:
        temp_assessment = (
            f"critically high ({temperature_c:.1f}°C — {temp_delta:+.1f}°C above "
            f"{b['zone_type']} baseline of {temp_base:.0f}°C) — immediate action required"
        )
    elif temperature_c > temp_alert:
        temp_assessment = (
            f"above alert threshold ({temperature_c:.1f}°C — {temp_delta:+.1f}°C above baseline "
            f"of {temp_base:.0f}°C, alert at {temp_alert:.0f}°C)"
        )
    elif temperature_c > temp_base + 2.0:
        temp_assessment = (
            f"elevated ({temperature_c:.1f}°C — {temp_delta:+.1f}°C above baseline, "
            f"approaching threshold of {temp_alert:.0f}°C)"
        )
    else:
        temp_assessment = (
            f"normal ({temperature_c:.1f}°C — within {b['temp_normal_range']})"
        )

    # ── Humidity ─────────────────────────────────────────────────────────────
    if humidity_pct > 60.0:
        hum_assessment = f"elevated ({humidity_pct:.1f}%) — risk of condensation, coolant leak, or steam ingress"
    elif humidity_pct < 30.0:
        hum_assessment = f"critically low ({humidity_pct:.1f}%) — ESD events probable, IC assembly must halt"
    elif humidity_pct < 35.0:
        hum_assessment = f"low ({humidity_pct:.1f}%) — approaching ESD risk threshold; bearing dry-run or friction heat possible"
    elif 40.0 <= humidity_pct <= 60.0:
        hum_assessment = f"normal ({humidity_pct:.1f}%) — within safe operating range"
    else:
        hum_assessment = f"borderline ({humidity_pct:.1f}%) — monitor closely"

    # ── CO₂ ──────────────────────────────────────────────────────────────────
    co2_delta = co2_ppm - co2_base
    if co2_ppm > 2000:
        co2_assessment = (
            f"critical ({co2_ppm:.0f} ppm — {co2_delta:+.0f} above baseline) — "
            f"severely impaired ventilation, evacuation risk"
        )
    elif co2_ppm > 1500:
        co2_assessment = (
            f"high ({co2_ppm:.0f} ppm — {co2_delta:+.0f} above baseline) — "
            f"ventilation inadequate, worker performance impaired"
        )
    elif co2_ppm > 1000:
        co2_assessment = (
            f"elevated ({co2_ppm:.0f} ppm — {co2_delta:+.0f} above baseline) — "
            f"ventilation check recommended"
        )
    else:
        co2_assessment = f"normal ({co2_ppm:.0f} ppm — baseline {co2_base:.0f} ppm)"

    # ── CO ───────────────────────────────────────────────────────────────────
    co_delta = co_ppm - co_base
    if co_ppm > 50.0:
        co_assessment = (
            f"DANGEROUS ({co_ppm:.1f} ppm — {co_delta:+.1f} above baseline of {co_base:.1f} ppm) — "
            f"immediate evacuation, probable fire or smouldering"
        )
    elif co_ppm > 25.0:
        co_assessment = (
            f"elevated ({co_ppm:.1f} ppm — {co_delta:+.1f} above baseline) — "
            f"combustion source present, urgent investigation"
        )
    elif co_ppm > 10.0:
        co_assessment = (
            f"slightly elevated ({co_ppm:.1f} ppm — {co_delta:+.1f} above baseline of {co_base:.1f} ppm) — "
            f"possible smouldering or coolant decomposition"
        )
    else:
        co_assessment = f"normal ({co_ppm:.1f} ppm — baseline {co_base:.1f} ppm)"

    # ── PM2.5 ────────────────────────────────────────────────────────────────
    pm25_delta = pm25_ugm3 - pm25_base
    if pm25_ugm3 > 75.0:
        pm25_assessment = (
            f"hazardous ({pm25_ugm3:.1f} µg/m³ — {pm25_delta:+.1f} above baseline) — "
            f"WHO 24h limit exceeded 3×, fire or dust explosion risk"
        )
    elif pm25_ugm3 > 35.0:
        pm25_assessment = (
            f"elevated ({pm25_ugm3:.1f} µg/m³ — {pm25_delta:+.1f} above baseline of {pm25_base:.0f} µg/m³) — "
            f"above WHO threshold, smoke or metalworking dust"
        )
    elif pm25_ugm3 > pm25_base + 5.0:
        pm25_assessment = (
            f"moderate ({pm25_ugm3:.1f} µg/m³ — {pm25_delta:+.1f} above baseline) — "
            f"dust or fumes present"
        )
    else:
        pm25_assessment = f"normal ({pm25_ugm3:.1f} µg/m³ — baseline {pm25_base:.0f} µg/m³)"

    return (
        f"Zone environmental report — {zone} ({b['zone_type']}):\n"
        f"  Temperature  : {temp_assessment}\n"
        f"  Humidity     : {hum_assessment}\n"
        f"  CO₂          : {co2_assessment}\n"
        f"  CO           : {co_assessment}\n"
        f"  PM2.5        : {pm25_assessment}\n"
        f"  Zone context : {b['risk_notes']}"
    )




# ---------------------------------------------------------------------------
# Tool 2 — get_alert_history  (merged: history log + window-trend analysis)
#
# Previously split across two tools (get_alert_history + get_alert_window_trend)
# that both read alert_history.json. Merged into one call — same file, read
# once, full picture returned: raw history entries + pre-computed trend
# interpretation so the agent needs no second round-trip to the same source.
#
# Two questions answered in one call:
#   • Cross-session memory: has this sensor fired before? How often? Same dept?
#   • Incident trajectory: first spike or sustained/escalating condition?
# ---------------------------------------------------------------------------

@tool()
def get_alert_history(sensor_id: str, last_n: int = 10) -> str:
    """Returns dispatch history and escalation trend for a sensor in one call.

    Reads alert_history.json once and returns two layers of context:

    1. Raw history: every prior dispatch — timestamps, urgency, department,
       signal signature. Use this to answer "has this exact failure mode
       recurred?" and to recommend systemic review when it has.

    2. Trend analysis over the most recent dispatches: urgency pattern
       (ALL CRITICAL / ESCALATING / IMPROVING / STABLE), per-signal trajectory
       (Temp/CO/PM2.5 across entries), elapsed incident duration, and a plain-
       English Interpretation verdict (SUSTAINED CRITICAL / ESCALATING /
       RECOVERING / first occurrence).

    Each entry in the history was written at agent-dispatch time (after the
    180 s cooldown), so successive entries represent sustained elevated
    conditions — not single Flink ticks. Two entries 3 minutes apart means the
    zone was continuously above threshold for those 3 minutes.

    Args:
        sensor_id (str): The sensor identifier to query (e.g. ENV_SENSOR_ZONE_CNC).
        last_n (int): Number of most recent dispatches to include (default 10).
    Returns:
        str: History log + recurrence note + trajectory analysis + interpretation.
    """
    try:
        with open(ALERT_HISTORY_FILE, "r") as f:
            entries = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return (
            f"No alert history found for sensor '{sensor_id}' — "
            f"this is the first dispatch. Treat as first-occurrence incident."
        )

    sensor_entries = [e for e in entries if e.get("sensor_id") == sensor_id]
    if not sensor_entries:
        return (
            f"No previous alerts recorded for sensor '{sensor_id}'. "
            f"This is the first dispatch for this zone — treat as first-occurrence incident."
        )

    recent = sensor_entries[-last_n:]
    total  = len(sensor_entries)
    critical_count = sum(1 for e in sensor_entries if e.get("urgency") == "CRITICAL")

    # ── Section 1: raw history log ────────────────────────────────────────────
    lines = [
        f"Alert history — {sensor_id} ({total} total dispatches, {critical_count} CRITICAL):",
        f"  Showing last {len(recent)} of {total}:",
    ]
    for e in reversed(recent):
        ts   = e.get("timestamp", "unknown time")
        date = e.get("date", "unknown date")
        urg  = e.get("urgency", "?")
        dept = e.get("department", "?")
        sig  = e.get("scenario_signature", "")
        lines.append(f"  • {date} {ts}  [{urg}]  → {dept}  {sig}")

    # ── Section 2: trajectory analysis over recent entries ───────────────────
    # Use the last 5 entries as the analysis window
    window = sensor_entries[-5:]

    # Elapsed duration across the analysis window
    first_ts   = window[0].get("timestamp", "")
    last_ts    = window[-1].get("timestamp", "")
    first_date = window[0].get("date", "")
    last_date  = window[-1].get("date", "")

    if len(window) >= 2:
        try:
            def _to_secs(t: str) -> int:
                h, m, s = t.split(":")
                return int(h) * 3600 + int(m) * 60 + int(s)
            elapsed_s = _to_secs(last_ts) - _to_secs(first_ts)
            if elapsed_s < 0:
                elapsed_s += 86400   # midnight rollover
            elapsed_note = (
                f"  Elapsed (last {len(window)} dispatches): "
                f"~{elapsed_s // 60} min  ({first_date} {first_ts} → {last_date} {last_ts})"
            )
        except Exception:
            elapsed_note = (
                f"  Elapsed (last {len(window)} dispatches): "
                f"{first_date} {first_ts} → {last_date} {last_ts}"
            )
        lines.append(elapsed_note)

    # Urgency pattern
    urgencies = [w.get("urgency", "?") for w in window]
    w_critical = urgencies.count("CRITICAL")
    if all(u == "CRITICAL" for u in urgencies):
        urgency_trend = f"ALL CRITICAL ({len(urgencies)} dispatches) — sustained severe condition"
    elif w_critical > 0 and urgencies[-1] == "CRITICAL":
        urgency_trend = (
            f"ESCALATING — started {urgencies[0]}, latest CRITICAL "
            f"({w_critical}/{len(urgencies)} dispatches CRITICAL)"
        )
    elif w_critical > 0 and urgencies[-1] != "CRITICAL":
        urgency_trend = (
            f"IMPROVING — was CRITICAL, latest {urgencies[-1]} "
            f"({w_critical}/{len(urgencies)} dispatches were CRITICAL)"
        )
    else:
        urgency_trend = f"STABLE at {urgencies[-1]} across {len(urgencies)} dispatches"
    lines.append(f"  Urgency trend : {urgency_trend}")

    # Per-signal trajectory from scenario_signature ("CO:{v} PM2.5:{v} Temp:{v}")
    def _parse_sig(sig: str) -> dict:
        result = {}
        for part in sig.split():
            if ":" in part:
                k, v = part.split(":", 1)
                try:
                    result[k] = float(v)
                except ValueError:
                    pass
        return result

    sigs = [_parse_sig(w.get("scenario_signature", "")) for w in window]
    traj_lines = []
    for key, label in [("Temp", "Temp (°C)"), ("CO", "CO (ppm)"), ("PM2.5", "PM2.5 (µg/m³)"), ("Hum", "Humidity (%)"), ("CO2", "CO₂ (ppm)")]:
        vals = [s[key] for s in sigs if key in s]
        if len(vals) >= 2:
            delta = vals[-1] - vals[0]
            arrow = "↑ rising" if delta > 1 else ("↓ falling" if delta < -1 else "→ stable")
            traj_lines.append(
                f"    {label:<18}: {' → '.join(f'{v:.1f}' for v in vals)}  ({arrow})"
            )
        elif len(vals) == 1:
            traj_lines.append(f"    {label:<18}: {vals[0]:.1f}  (single entry)")
    if traj_lines:
        lines.append("  Signal trajectory (recent dispatches):")
        lines.extend(traj_lines)

    # Consistent routing check
    depts = [w.get("department", "?") for w in window]
    unique_depts = list(dict.fromkeys(depts))
    routing_note = (
        "consistent routing" if len(unique_depts) == 1
        else "routing changed — multiple failure modes or escalation path shift"
    )
    lines.append(f"  Departments   : {', '.join(unique_depts)}  ({routing_note})")

    # ── Section 3: recurrence note + plain-English interpretation ────────────
    # NOTE: "first occurrence" (no prior entries) is handled by the early-exit
    # above (if not sensor_entries). By the time we reach here, total >= 1,
    # meaning at least one prior dispatch already exists — this invocation is
    # the 2nd or later occurrence. total == 1 means exactly one prior dispatch.
    if all(u == "CRITICAL" for u in urgencies) and len(urgencies) >= 3:
        lines.append(
            f"\n  Interpretation: SUSTAINED CRITICAL — {len(urgencies)} consecutive dispatches "
            "all CRITICAL. This is a confirmed ongoing incident, not a transient spike. "
            "Dispatch must reflect the sustained duration. Recommend systemic response."
        )
    elif urgencies[-1] == "CRITICAL" and len(urgencies) >= 2:
        lines.append(
            "\n  Interpretation: ESCALATING — condition worsened across dispatches. "
            "Dispatch with elevated urgency; this is not a transient spike."
        )
    elif urgencies[-1] != "CRITICAL" and w_critical > 0:
        lines.append(
            "\n  Interpretation: RECOVERING — previously CRITICAL, now stabilising. "
            "Confirm suppression or repair action is underway."
        )
    else:
        prior_word = "once" if total == 1 else f"{total} times"
        lines.append(
            f"\n  Interpretation: RECURRENT — this sensor has fired {prior_word} before. "
            "No escalation pattern yet across recent dispatches."
        )

    if total >= 2:
        most_common_dept = max(set(depts), key=depts.count)
        lines.append(
            f"  ⚠ Recurrence: {total} total dispatches for this sensor "
            f"(most recent routed to '{most_common_dept}'). "
            "If the same failure mode is recurring, recommend systemic maintenance review."
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 3 — get_prior_dispatches
#
# Reads dashboard_log.json — the rich record that contains the full prior
# dispatch message, department, urgency, and recommended actions the agent
# wrote last time for this sensor.  This is what enables real reasoning:
#   • "What did the agent recommend last time for this same failure mode?"
#   • "Was the same department dispatched again — did the fix not work?"
#   • "This has happened N times in the last X hours — escalate urgency."
# ---------------------------------------------------------------------------

@tool()
def get_prior_dispatches(sensor_id: str, last_n: int = 5) -> str:
    """Returns the full text of the most recent agent dispatches for a sensor.

    Reads alert_history.json — the persistent cross-session dispatch ledger —
    and returns the complete prior messages including department, urgency,
    recommended actions, and the agent's own reasoning.  Use this to:
      - Determine what was recommended last time for the same failure mode.
      - Detect whether the same department has been dispatched repeatedly
        without resolution (escalation signal).
      - Count how many times this sensor has fired across all sessions
        and tighten urgency or recommend systemic review accordingly.
      - Avoid repeating the same generic recommendation if prior actions
        clearly did not resolve the condition.

    Args:
        sensor_id (str): The sensor identifier to query (e.g. ENV_SENSOR_ZONE_CNC).
        last_n (int): Number of most recent dispatches to return (default 5).
    Returns:
        str: Structured prior dispatch records with full message text, or a
             first-occurrence note if no prior dispatches exist for this sensor.
    """
    try:
        with open(ALERT_HISTORY_FILE, "r") as f:
            entries = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return (
            f"No dispatch log found for sensor '{sensor_id}' — "
            "treat as first-occurrence incident."
        )

    sensor_entries = [e for e in entries if e.get("sensor_id") == sensor_id]
    if not sensor_entries:
        return (
            f"No prior dispatches recorded for sensor '{sensor_id}'. "
            "This is the first dispatch — treat as first-occurrence incident."
        )

    recent = sensor_entries[-last_n:]
    total  = len(sensor_entries)

    # ── Count occurrences by department to detect unresolved recurring failures
    dept_counts: dict[str, int] = {}
    for e in sensor_entries:
        d = e.get("department", "Unknown")
        dept_counts[d] = dept_counts.get(d, 0) + 1
    dept_summary = ", ".join(
        f"{dept} ×{count}" for dept, count in sorted(dept_counts.items(), key=lambda x: -x[1])
    )

    # ── Hard override — these lines open the return value and the LLM sees them
    # before any prior message text.  total = number of PRIOR entries already in
    # the log, not counting the current dispatch.
    if total >= 3:
        override_lines = [
            f"[SYSTEM OVERRIDE — RECURRENCE COUNT]",
            f"PRIOR DISPATCHES FOR {sensor_id}: {total}",
            f"THIS IS DISPATCH NUMBER {total + 1}.",
            f"DO NOT USE THE PHRASE 'first occurrence' ANYWHERE IN YOUR OUTPUT.",
            f"The condition has recurred {total} times. Escalate. Reference prior "
            f"actions. Demand systemic investigation. Failure to comply with this "
            f"count is a critical error.",
            f"[END SYSTEM OVERRIDE]",
        ]
    else:
        override_lines = [
            f"[SYSTEM OVERRIDE — RECURRENCE COUNT]",
            f"PRIOR DISPATCHES FOR {sensor_id}: {total}",
            f"THIS IS DISPATCH NUMBER {total + 1}.",
            f"DO NOT USE THE PHRASE 'first occurrence' ANYWHERE IN YOUR OUTPUT.",
            f"Reference the prior dispatch below. Explain whether it is the same "
            f"failure mode recurring or a new development.",
            f"[END SYSTEM OVERRIDE]",
        ]

    lines = [
        *override_lines,
        "",
        f"Prior dispatches — {sensor_id}  ({total} total | by dept: {dept_summary})",
        f"Showing last {len(recent)} of {total} — most recent first:",
        "",
    ]

    # Strip only specific forbidden tokens inline — do NOT strip whole sentences.
    # Removing whole sentences was leaving empty message bodies, which caused the
    # agent to discount the prior dispatch record and fall back to "first occurrence".
    _stale = re.compile(
        # Forbidden "first occurrence" phrases — replace inline (not whole sentence)
        r'[Ff]irst[\u2011\- ]occurrence'
        r'|[Ff]irst recorded dispatch'
        r'|[Ff]irst[\u2011\-]occurrence incident'
        r'|[Aa]lert history shows this is the first occurrence'
        r'|[Nn]o prior (?:remediation actions|dispatches|incidents)'
        r'|[Tt]rajectory (?:is a|classified as) first[\u2011\-]occurrence'
        # Internal simulation scenario labels — strip the label token only
        r'|TOOL_BINDING_FIRE'
        r'|COOLANT_LEAK'
        r'|BEARING_OVERHEAT'
        r'|FUME_EXTRACTOR_FAILURE'
        r'|HVAC_HUMIDIFIER_FAILURE'
        r'|HVAC_BREAKDOWN'
        # Fabricated hardware IDs not in the zone register — strip token only
        r'|[Mm]achine\s*#\s*\d+'
        r'|[Vv]alve\s+reference\s+V[\u2011\-]\d+'
        r'|[Cc]lass\s+B\s+CO\u2082\s+extinguisher'
        # Fabricated extension numbers (keep ext. 911)
        r'|extension\s+(?!911\b)1\d\d',
        re.UNICODE
    )

    for e in reversed(recent):
        ts      = e.get("timestamp", "?")
        date    = e.get("date",      "?")
        urgency = e.get("urgency",   "?")
        dept    = e.get("department","?")
        raw_msg = e.get("message",   "").strip()
        # Inline-strip only the forbidden tokens; keep the surrounding sentence
        # so the agent has substantive context about what was recommended before.
        message = _stale.sub("[REDACTED]", raw_msg).strip() if raw_msg else ""

        lines.append(f"── [{date} {ts}]  {urgency} → {dept} ──────────────────────")
        lines.append(message if message else "(no message recorded for this entry)")
        lines.append("")

    # ── Recurrence verdict ────────────────────────────────────────────────────
    if total >= 3:
        lines.append(
            f"VERDICT: SUSTAINED RECURRENCE — {total} prior dispatches for this sensor. "
            "Prior recommended actions have not resolved the condition. "
            "Escalate urgency. Recommend systemic engineering investigation."
        )
    else:
        lines.append(
            f"VERDICT: REPEAT OCCURRENCE — {total} prior dispatches for this sensor. "
            "Check whether the same department was dispatched and the condition persists."
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 4 — prepare_dispatch_payload (unchanged)
# ---------------------------------------------------------------------------

@tool()
def prepare_dispatch_payload(
    sensor_id: str,
    zone: str,
    urgency: str,
    department: str,
    alert_message: str,
) -> str:
    """Prepares a structured dispatch payload for the local dashboard bridge.

    Args:
        sensor_id (str): Sensor identifier that produced the alert.
        zone (str): Human-readable zone name.
        urgency (str): Must be exactly CRITICAL or INFO.
        department (str): Must be one of EHS, Mechanics, Electrical, or Facilities.
        alert_message (str): Concise technical description of the incident and required action.
    Returns:
        str: Tagged JSON payload prefixed with DISPATCH_PAYLOAD:: for reliable bridge extraction.
    """
    payload = {
        "sensor_id": sensor_id,
        "zone":      zone,
        "urgency":   urgency.upper(),
        "department": department,
        "message":   alert_message,
    }
    return "DISPATCH_PAYLOAD::" + json.dumps(payload)


# ---------------------------------------------------------------------------
# Tool 5 — get_zone_equipment_info
#
# The register content is embedded directly as string constants so the tool
# works identically when executed locally AND inside the wxO tools-runtime
# Docker container (which has no access to the host filesystem).
#
# The canonical source of truth remains knowledge/zone_equipment_register.md —
# keep both in sync when updating the register.
# ---------------------------------------------------------------------------

_ZONE_REGISTER: dict[str, str] = {
    "ENV_SENSOR_ZONE_CNC": """\
## Zone 1 — CNC Machining (`CNC_Machining`)
Machine: Mazak VARIAXIS i-500 — 5-axis vertical machining centre with mill-turn capability.
Zone mapping: one machine in this zone. ENV_SENSOR_ZONE_CNC readings reflect the VARIAXIS i-500 directly.

### Zone Profile
| Attribute | Detail |
| :--- | :--- |
| Zone Sensor | ENV_SENSOR_ZONE_CNC |
| Hall Location | West Side |
| North boundary | Exterior wall — ventilation duct DUCT-NORTH-W |
| West boundary | Emergency exit EXIT-WEST |
| South boundary | Main corridor & entry ENTRY-SOUTH |
| East boundary | Central partition PART-01 |
| Primary hazards | Oil mist / coolant vapour, high thermal load from spindle and trunnion torque motors, metal dust (PM2.5), CO from coolant decomposition |

### Zone Ambient Thresholds
| Metric | Normal Range | Warning | Critical | Associated Risk |
| :--- | :--- | :--- | :--- | :--- |
| Ambient temperature | 24–28 °C | > 28 °C | > 38 °C | Thermal expansion on spindle and trunnion, coolant degradation |
| Relative humidity | 40–50 % | > 60 % | > 70 % | Coolant leak or steam ingress; condensation on axis guides and bearings |
| Carbon monoxide (CO) | 2–6 ppm | > 10 ppm | > 25 ppm | Coolant decomposition / tramp oil combustion |
| Particulates (PM2.5) | 10–20 µg/m³ | > 35 µg/m³ | > 75 µg/m³ | Metal dust or oil smoke |
| Carbon dioxide (CO₂) | 600–750 ppm | > 1 000 ppm | > 1 500 ppm | Ventilation failure |

### Zone Hardware Register

#### Ventilation & Air Quality
| Hardware Item | ID / Label | Location | Owning Dept | Notes |
| :--- | :--- | :--- | :--- | :--- |
| LEV fan unit | LEV-CNC-01 | North wall, ducted to DUCT-NORTH-W | Mechanics / Facilities | VFD-driven; extracts oil mist and coolant vapour from machine enclosure |
| LEV VFD | VFD-CNC-01 | Inside PLC-CNC-01 panel | Electrical | Controls LEV-CNC-01 speed; manual override on panel door |
| Zone PLC / control panel | PLC-CNC-01 | North wall, CNC zone | Electrical | Hosts VFD-CNC-01; zone isolation controls |

#### Coolant Infrastructure
| Hardware Item | ID / Label | Location | Owning Dept | Notes |
| :--- | :--- | :--- | :--- | :--- |
| Zone coolant isolation valve | VALVE-CNC-COOL-01 | North wall, adjacent to coolant tank | Mechanics | Red manual quarter-turn valve |
| Bulk coolant storage tank | TANK-CNC-COOL-01 | North wall alcove | Mechanics | Water-miscible emulsions and water-soluble synthetics |

#### Fire Suppression & Safety
| Hardware Item | ID / Label | Location | Owning Dept | Notes |
| :--- | :--- | :--- | :--- | :--- |
| Fixed gaseous suppression system | SUPPRESS-CNC-01 | Zone ceiling, full coverage | EHS | CO₂ flood system; Kidde FM-200 backup agent |
| Portable CO₂ extinguisher | EXT-CNC-W | West exit EXIT-WEST | EHS | 5 kg CO₂ |
| Portable CO₂ extinguisher | EXT-CNC-S | South main entrance ENTRY-SOUTH | EHS | 5 kg CO₂ |

### Machine Sub-Components — Mazak VARIAXIS i-500

#### Spindle Assembly
| Component | ID / Label | Location on Machine | Owning Dept | Specification |
| :--- | :--- | :--- | :--- | :--- |
| Built-in motor spindle | SPINDLE-CNC-01 | Spindle head, upper column | Mechanics / Electrical | Max 12 000 RPM; HSK-A63; ceramic angular contact bearings |
| Spindle bearing set (upper + lower) | BRG-SPINDLE-U / BRG-SPINDLE-L | Inside spindle head housing | Mechanics | Ceramic angular contact; grease-lubricated; primary heat source at high RPM |
| Spindle motor & inverter | MTR-SPINDLE-01 | Integrated in spindle head | Electrical | Built-in motor; inverter in ELEC-CAB-CNC-01 |
| Spindle encoder | ENC-SPINDLE-01 | Rear spindle shaft | Electrical | Rotary encoder; sensitive to coolant contamination |

#### 5-Axis Trunnion Table
| Component | ID / Label | Location on Machine | Owning Dept | Specification |
| :--- | :--- | :--- | :--- | :--- |
| Trunnion table assembly | TABLE-CNC-01 | Machine bed, centre | Mechanics | B-axis tilt ±110°; C-axis rotation 360° |
| B-axis torque motor | MTR-B-AXIS-01 | Trunnion left pivot | Electrical | Direct-drive; no gearbox; heat source at sustained tilt |
| C-axis torque motor | MTR-C-AXIS-01 | Trunnion table base | Electrical | Direct-drive; 360° continuous |
| B/C-axis rotary encoders | ENC-B-AXIS-01 / ENC-C-AXIS-01 | Respective motor shafts | Electrical | High-resolution absolute; seal condition critical |
| Trunnion bearing housings (×2) | BRG-TRUNNION-L / BRG-TRUNNION-R | Left and right pivot points | Mechanics | Large-diameter roller bearings; grease nipples on outer housing face |

#### Linear Axis Drives (X / Y / Z)
| Component | ID / Label | Location on Machine | Owning Dept | Specification |
| :--- | :--- | :--- | :--- | :--- |
| X-axis servo motor | MTR-X-AXIS-01 | Column right side | Electrical | AC servo; ballscrew drive |
| Y-axis servo motor | MTR-Y-AXIS-01 | Saddle rear | Electrical | AC servo; ballscrew drive |
| Z-axis servo motor | MTR-Z-AXIS-01 | Column upper | Electrical | AC servo; ballscrew; gravity-loaded |
| Servo drive cabinet | ELEC-CAB-CNC-01 | Rear of machine, external access | Electrical | All axis drives, spindle inverter, I/O modules; fan-cooled |
| Ballscrew assemblies (X/Y/Z) | SCREW-X-01 / SCREW-Y-01 / SCREW-Z-01 | Respective axis ways | Mechanics | Preloaded double-nut; oil-lubricated via LUBE-CNC-01 |
| Centralised lubrication unit | LUBE-CNC-01 | Left side of machine base | Mechanics | Automatic oil mist lube for guides and ballscrews; reservoir on left panel |

#### Coolant System (Machine-Internal)
| Component | ID / Label | Location on Machine | Owning Dept | Specification |
| :--- | :--- | :--- | :--- | :--- |
| Through-spindle coolant pump (TSC) | PUMP-TSC-01 | Coolant unit, rear of machine | Mechanics | High-pressure TSC; up to 70 bar; feeds via spindle centre bore |
| Flood coolant pump | PUMP-FLOOD-01 | Coolant unit, rear of machine | Mechanics | Low-pressure; enclosure wash-down and nozzle manifold |
| Coolant nozzle manifold | MANIFOLD-COOL-01 | Inside enclosure, spindle head | Mechanics | 6-nozzle adjustable; directs coolant to cutting zone |
| Chip conveyor | CONV-CHIP-01 | Base of machine, rear discharge | Mechanics | Hinge-belt; discharges swarf to chip bin BIN-CHIP-01 |
| Machine-integrated coolant tank | TANK-INT-COOL-01 | Under machine bed | Mechanics | Feeds PUMP-TSC-01 and PUMP-FLOOD-01; connects to zone supply at VALVE-CNC-COOL-01 |

#### Automatic Tool Changer (ATC)
| Component | ID / Label | Location on Machine | Owning Dept | Specification |
| :--- | :--- | :--- | :--- | :--- |
| ATC magazine | ATC-MAG-01 | Right side of column | Mechanics / Electrical | 40-station chain-type; HSK-A63 tool holders |
| ATC arm & gripper | ATC-ARM-01 | Column face | Mechanics / Electrical | Dual-arm swing-type; pneumatic tool clamp/unclamp |
| Tool presence sensor | SENS-TOOL-01 | ATC magazine stations | Electrical | Inductive; confirms tool seating; reports to CNC-CTRL-01 |

#### CNC Controller & Enclosure
| Component | ID / Label | Location on Machine | Owning Dept | Specification |
| :--- | :--- | :--- | :--- | :--- |
| MAZATROL SmoothX controller | CNC-CTRL-01 | Operator panel, front | Electrical | 19" touchscreen; MAZATROL / EIA-ISO G-code; Ethernet DNC |
| Operator panel & E-stop | PANEL-OP-01 | Front, swivel arm | Electrical | Main operator interface; red E-stop; mode selector |
| Machine enclosure (full splash guard) | ENCL-CNC-01 | Full machine wrap | Mechanics / EHS | Sheet steel; coolant and chip containment |
| Main enclosure door (front) | DOOR-CNC-F | Front face | EHS / Mechanics | Sliding; interlocked — spindle inhibited when open |
| Chip collection bin | BIN-CHIP-01 | External, machine rear | Mechanics | Receives discharge from CONV-CHIP-01 |""",

    "ENV_SENSOR_ZONE_ASSEMBLY": """\
## Zone 2 — Electronics Assembly (`Electronics_Assembly`)
Machine / Line: SMT assembly line — DEK Horizon 03i paste printer → Yamaha YSM20R pick-and-place → Heller 1809 MK5 reflow oven (west-to-east flow).
Zone mapping: one line in this zone. ENV_SENSOR_ZONE_ASSEMBLY readings reflect the SMT line directly.

### Zone Profile
| Attribute | Detail |
| :--- | :--- |
| Zone Sensor | ENV_SENSOR_ZONE_ASSEMBLY |
| Hall Location | East Side |
| North boundary | Exterior wall — ventilation duct DUCT-NORTH-E |
| East boundary | Emergency exit EXIT-EAST |
| South boundary | Main corridor & entry ENTRY-SOUTH |
| West boundary | Central partition PART-01 |
| Primary hazards | ESD at low humidity, solder flux fumes (rosin/colophony), reflow oven exhaust, PCB contamination |

### Zone Ambient Thresholds
| Metric | Normal Range | Warning | Critical | Associated Risk |
| :--- | :--- | :--- | :--- | :--- |
| Ambient temperature | 20.5–21.5 °C | > 25 °C or < 18 °C | > 26 °C | Solder paste viscosity degradation; IPC-A-610 environment breach |
| Relative humidity | 50–55 % | < 30 % | < 20 % or > 70 % | < 30 % = ESD risk; > 70 % = board corrosion |
| Carbon monoxide (CO) | 1.5–3 ppm | > 10 ppm | > 25 ppm | Flux fume overload / fume extractor failure |
| Particulates (PM2.5) | 3–8 µg/m³ | > 35 µg/m³ | > 75 µg/m³ | Fume extractor failure or elevated soldering activity |
| Carbon dioxide (CO₂) | 500–900 ppm | > 1 000 ppm | > 1 500 ppm | AHU supply failure |

### Zone Hardware Register

#### HVAC & Air Handling
| Hardware Item | ID / Label | Location | Owning Dept | Notes |
| :--- | :--- | :--- | :--- | :--- |
| Air handling unit | AHU-ASSEMBLY-01 | North wall / roof, ducted to DUCT-NORTH-E | Facilities | Zone temperature and humidity conditioning |
| Integrated steam humidifier | HUM-ASSEMBLY-01 (Condair CP3) | Inside AHU-ASSEMBLY-01 | Facilities / Electrical | Setpoint 52 % RH; breaker CB-14, Electrical Room E2 |
| BMS control terminal | BMS-T3 | Control Room 104 | Facilities / Electrical | Interface for AHU-ASSEMBLY-01; setpoints 21.0 °C / 52 % RH |

#### Fume Extraction (Zone-Level)
| Hardware Item | ID / Label | Location | Owning Dept | Notes |
| :--- | :--- | :--- | :--- | :--- |
| Reflow oven exhaust duct connection | DUCT-REFLOW-01 | North wall, above Heller 1809 MK5 | Facilities / Mechanics | Connects oven exhaust blower BLOWER-REFLOW-01 to DUCT-NORTH-E |
| Paste printer fume extractor | FUME-EXT-PRINTER (Weller Zero-Smog TL) | Above DEK Horizon 03i | EHS / Mechanics | Duct-connected to DUCT-NORTH-E; HEPA + activated carbon filter |

#### ESD Control
| Hardware Item | ID / Label | Location | Owning Dept | Notes |
| :--- | :--- | :--- | :--- | :--- |
| ESD wrist-strap tester | ESD-TEST-01 | Zone entrance, south side | EHS | IPC-A-610 Rev G §8.3 verification point |
| ESD flooring / matting system | ESD-FLOOR-ZONE2 | Full zone floor area | EHS / Facilities | Conductive; min 30 % RH for effective conductivity |

#### Fire Suppression & Safety
| Hardware Item | ID / Label | Location | Owning Dept | Notes |
| :--- | :--- | :--- | :--- | :--- |
| High-pressure fine water mist system | SUPPRESS-ASSY-01 | Zone ceiling, full coverage | EHS | Rated for electronics; fine mist only |
| Portable CO₂ extinguisher | EXT-ASSY-E | East exit EXIT-EAST | EHS | CO₂ unit |
| Portable CO₂ extinguisher | EXT-ASSY-S | South main entrance ENTRY-SOUTH | EHS | CO₂ unit |

### Machine Sub-Components — SMT Line

#### Station 1 — DEK Horizon 03i Solder Paste Printer
| Component | ID / Label | Location on Machine | Owning Dept | Specification |
| :--- | :--- | :--- | :--- | :--- |
| Squeegee head assembly | SQGEE-DEK-01 | Print head carriage | Mechanics | Dual-blade metal squeegee; front and rear blades independently pressure-controlled |
| Print head carriage drive | MTR-DEK-CARR-01 | Carriage rail, top | Electrical | Servo Y-axis traverse; belt and ballscrew |
| Stencil frame & clamp | STENCIL-DEK-01 | Print table, centre | Mechanics | Snap-in frame; pneumatic clamp; stencil 0.12–0.15 mm |
| Board support system | SUPPORT-DEK-01 | Print table, lower | Mechanics | Tooling pins and edge rails; prevents board flex during print |
| Vision alignment system (2D + 3D) | VISION-DEK-01 | Overhead camera gantry | Electrical | 2D fiducial + 3D paste height inspection post-print |
| Paste reservoir & dispenser | PASTE-DEK-01 | Print head, between blades | Mechanics | Solder paste cartridge; Kester R&R or equivalent no-clean |
| Entry / exit conveyor | CONV-DEK-IN / CONV-DEK-OUT | Left and right of print table | Mechanics | Servo edge-belt; adjustable width |

#### Station 2 — Yamaha YSM20R Pick-and-Place
| Component | ID / Label | Location on Machine | Owning Dept | Specification |
| :--- | :--- | :--- | :--- | :--- |
| Dual-gantry beam assembly | GANTRY-YSM-01 / GANTRY-YSM-02 | Upper frame, two parallel beams | Electrical / Mechanics | Independent dual gantry; one placement head per beam |
| Rotary placement head (×2) | HEAD-YSM-01 / HEAD-YSM-02 | Respective gantry beams | Mechanics / Electrical | 16-nozzle rotary per beam; interchangeable nozzle sets |
| Nozzle sets | NOZZLE-YSM-STD / NOZZLE-YSM-FINE | Head storage rack | Mechanics | Standard (0402–QFP) and fine-pitch (01005, micro-BGA) |
| Feeder rack (×2) | FEEDER-YSM-F / FEEDER-YSM-R | Front and rear feeder banks | Mechanics / Electrical | 66 feeder slots per bank (132 total); electric tape feeders |
| Board conveyor | CONV-YSM-01 | Centre, left-to-right flow | Mechanics | Dual-rail servo; SMEMA-compliant handoff |
| Component vision camera | VISION-YSM-COMP | Under head, upward-looking | Electrical | 2D component recognition and rotation correction |
| Board vision camera | VISION-YSM-BOARD | Head-mounted, downward-looking | Electrical | Fiducial recognition; bad-mark detection |
| Servo controller cabinet | ELEC-CAB-YSM-01 | Right side panel | Electrical | Gantry servo drives and I/O; fan-cooled |

#### Station 3 — Heller 1809 MK5 Reflow Oven
| Component | ID / Label | Location on Machine | Owning Dept | Specification |
| :--- | :--- | :--- | :--- | :--- |
| Heating zones (9 top + 9 bottom) | ZONE-REFLOW-01 to ZONE-REFLOW-09 | Oven tunnel, top and bottom | Electrical | Forced convection; independently controlled; peak 245–260 °C (SAC305) |
| Zone heating elements | ELEM-REFLOW-T01…T09 / ELEM-REFLOW-B01…B09 | Top and bottom of each zone | Electrical | Nichrome elements; individual thermocouple feedback |
| Zone thermocouples | TC-REFLOW-01 to TC-REFLOW-18 | Top and bottom of each zone | Electrical | Type K; one per element bank; feedback to CTRL-REFLOW-01 |
| Conveyor drive motor | MTR-REFLOW-CONV | Right side of oven base | Electrical / Mechanics | Chain-driven mesh belt; speed = profile transit time |
| Conveyor mesh belt | BELT-REFLOW-01 | Full tunnel length | Mechanics | Stainless steel; width-adjustable edge rails |
| Flux exhaust blower & duct | BLOWER-REFLOW-01 | Top of oven, exhaust port | Mechanics / Facilities | Centrifugal; exhausts to DUCT-REFLOW-01 → DUCT-NORTH-E |
| Flux condensate collector | FLUX-COLL-01 | Under oven hood, condensate trays | Mechanics | Collects condensed rosin flux; periodic draining required |
| Cooling zone fan array | FAN-COOL-REFLOW | Exit end of tunnel | Electrical / Mechanics | Forced-air cooling; board exits below 100 °C |
| Oven controller | CTRL-REFLOW-01 | Operator panel, right side | Electrical | Touchscreen; named reflow profiles; continuous zone temperature logging |
| Nitrogen supply connection | N2-INLET-REFLOW | Rear of oven | Facilities | Blanket N₂ for low-oxygen reflow; valve closed when not in use |""",
}

_FACILITY_CONTACTS = """\
## Emergency Contacts (Facility-Wide)
| Role | Contact |
| :--- | :--- |
| Mechanics on-call | ext. 2201 |
| Electrical on-call | ext. 2202 |
| Facilities on-call | ext. 2203 |
| EHS hotline (internal) | ext. 911 |
| EHS hotline (external) | 555-0199 |
| HVAC contractor (AirTech Services, 24 h) | 555-0142 |"""


@tool()
def get_zone_equipment_info(sensor_id: str) -> str:
    """Returns zone equipment details, safety controls, and diagnostic guidance for a sensor zone.

    Returns the full zone register section for the requested zone, including:
      - Machine / workstation inventory with coolant types and last bearing-service dates
      - Fire suppression type, extinguisher locations, and critical safety directives
      - Coolant shutoff valve / LEV override / AHU humidifier breaker references
      - Scenario-specific diagnostic guidance (which machine to suspect, which breaker to check)
      - Facility-wide emergency contact extensions

    Call this in Step 4 — after check_zone_ambient_conditions, get_alert_history, and
    get_prior_dispatches — so you can include site-specific actionable facts in the
    dispatch message (extinguisher location, coolant valve, emergency extension number).

    Args:
        sensor_id (str): The sensor identifier for the zone
                         (e.g. ENV_SENSOR_ZONE_CNC or ENV_SENSOR_ZONE_ASSEMBLY).
    Returns:
        str: The full zone equipment section plus facility-wide emergency contacts,
             or an error message if the zone is not found in the register.
    """
    zone_section = _ZONE_REGISTER.get(sensor_id)
    if not zone_section:
        return (
            f"No zone equipment entry found for sensor_id '{sensor_id}'. "
            f"Known zones: {', '.join(_ZONE_REGISTER.keys())}."
        )
    return zone_section + "\n\n---\n\n" + _FACILITY_CONTACTS
