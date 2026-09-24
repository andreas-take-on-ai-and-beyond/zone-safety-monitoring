import json
import os
import sys
import threading
import time
from datetime import datetime

from confluent_kafka import Consumer

from wxo_client import extract_log_fields, invoke_wxo_agent

ROOT_DIR             = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_FILE             = os.path.join(ROOT_DIR, "dashboard_log.json")
SENSOR_LOG_FILE      = os.path.join(ROOT_DIR, "sensor_log.json")
ALERT_HISTORY_FILE   = os.path.join(ROOT_DIR, "alert_history.json")   # persistent cross-session dispatch history (never trimmed)
MAX_LOG_ENTRIES      = 500
BRIDGE_MODE          = "wxo"
_DEBUG_DUMP          = os.getenv("WXO_DEBUG_DUMP", "0") == "1"

# ---------------------------------------------------------------------------
# Alert cooldown — suppress re-triggering the agent for the same sensor
# within COOLDOWN_SECONDS after the last dispatch.
#
# Rationale: Flink fires on every 5-second reading that exceeds a threshold.
# Without a cooldown, a single heating event that takes 4 minutes to peak
# produces ~48 LLM calls, all describing the same incident.
#
# Real-world equivalent: "re-alarm delay" or "deadband timer" in SCADA/DCS
# systems (ABB 800xA, Honeywell Experion, Siemens PCS 7).
#
# COOLDOWN_SECONDS can be overridden per deployment via the environment variable.
# Default: 300 s (5 min) — one LLM dispatch per incident window per sensor.
# ---------------------------------------------------------------------------
COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "180"))
_last_alert_time: dict[str, float] = {}

# In-memory dispatch counter — incremented before each agent call so the
# recurrence status in the prompt is always accurate, even when alert_history.json
# hasn't been flushed yet (eliminates the "first occurrence" race condition for
# rapid successive dispatches at session start).
# Seeded from alert_history.json at startup so bridge restarts are transparent.
_dispatch_count: dict[str, int] = {}


def _seed_dispatch_count() -> None:
    """Pre-populate _dispatch_count from alert_history.json so that a bridge
    restart does not reset the per-sensor recurrence counter to zero.
    Called once at startup before the Kafka consumer loop begins.
    """
    try:
        with open(ALERT_HISTORY_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    sid = entry.get("sensor_id")
                    if sid:
                        _dispatch_count[sid] = _dispatch_count.get(sid, 0) + 1
                except json.JSONDecodeError:
                    pass
        if _dispatch_count:
            print("📋 Seeded dispatch counts from alert_history.json:")
            for sid, count in _dispatch_count.items():
                print(f"   {sid}: {count} prior dispatch(es)")
    except FileNotFoundError:
        pass  # no history yet — first ever run, counts stay at 0


_seed_dispatch_count()


def _is_suppressed(sensor_id: str) -> bool:
    """Return True if this sensor fired too recently and should be skipped."""
    now = time.time()
    last = _last_alert_time.get(sensor_id, 0.0)
    elapsed = now - last
    if elapsed < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - elapsed)
        print(f"⏳ [{sensor_id}] suppressed — cooldown active ({remaining}s remaining)")
        return True
    _last_alert_time[sensor_id] = now
    return False


conf = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'wxo-trigger-group',
    'auto.offset.reset': 'latest'
}


def _append_log(entry: dict) -> None:
    try:
        with open(LOG_FILE, "r") as f:
            lines = [line for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        lines = []

    lines.append(json.dumps(entry) + "\n")

    if len(lines) > MAX_LOG_ENTRIES:
        lines = lines[-MAX_LOG_ENTRIES:]

    with open(LOG_FILE, "w") as f:
        f.writelines(lines)


def _append_sensor_log(raw: dict) -> None:
    """Append one raw sensor tick to sensor_log.json (no cooldown filter).

    Only keeps the fields relevant for time-series charting — avoids
    bloating the file with the large env_report / reasoning strings.
    """
    entry = {
        "timestamp":     raw.get("timestamp", datetime.now().strftime("%H:%M:%S")),
        "sensor_id":     raw.get("sensor_id", "UNKNOWN"),
        "zone":          raw.get("zone", "UNKNOWN"),
        "temperature_c": raw.get("temperature_c"),
        "humidity_pct":  raw.get("humidity_pct"),
        "pressure_hpa":  raw.get("pressure_hpa"),
        "co2_ppm":       raw.get("co2_ppm"),
        "co_ppm":        raw.get("co_ppm"),
        "pm25_ugm3":     raw.get("pm25_ugm3"),
    }
    try:
        with open(SENSOR_LOG_FILE, "r") as f:
            lines = [line for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        lines = []

    lines.append(json.dumps(entry) + "\n")

    with open(SENSOR_LOG_FILE, "w") as f:
        f.writelines(lines)


def _append_alert_history(alert_data: dict, resolved: dict | None = None) -> None:
    """Append one dispatch to alert_history.json — append-only, never trimmed.

    Permanent cross-session ledger — survives dashboard_log.json resets between
    demo runs. Writes the full dispatch record (identical richness to dashboard_log)
    so get_prior_dispatches can reason over the complete history across all sessions.

    Args:
        alert_data: Raw Flink alert message — always the source of signal floats.
        resolved:   Agent-resolved fields (urgency, department, message, reasoning,
                    env_report) from extract_log_fields (wxO mode), or None (local mode).
    """
    meta = resolved if resolved is not None else alert_data

    def _fmt(val) -> str:
        try:
            return f"{float(val):.1f}"
        except (TypeError, ValueError):
            return "?"

    record = {
        "date":               datetime.now().strftime("%Y-%m-%d"),
        "timestamp":          datetime.now().strftime("%H:%M:%S"),
        "sensor_id":          alert_data.get("sensor_id", "UNKNOWN"),
        "zone":               alert_data.get("zone", "UNKNOWN"),
        "urgency":            meta.get("urgency", "INFO"),
        "department":         meta.get("department", "Facilities"),
        # Compact signal signature — used by get_alert_history for trajectory analysis
        "scenario_signature": (
            f"CO:{_fmt(alert_data.get('co_ppm'))} "
            f"PM2.5:{_fmt(alert_data.get('pm25_ugm3'))} "
            f"Temp:{_fmt(alert_data.get('temperature_c'))} "
            f"Hum:{_fmt(alert_data.get('humidity_pct'))} "
            f"CO2:{_fmt(alert_data.get('co2_ppm'))}"
        ),
        # Full dispatch content — used by get_prior_dispatches for recurrence reasoning
        "message":            meta.get("message",    ""),
        "reasoning":          meta.get("reasoning",  ""),
        "env_report":         meta.get("env_report", ""),
    }
    # Guard: if the file exists and does not end with '\n', write one first.
    # This prevents two JSON objects being concatenated on the same line if a
    # previous write was made without a trailing newline (e.g. from an older
    # version of this function or a manual edit).
    try:
        with open(ALERT_HISTORY_FILE, "rb") as _f:
            _f.seek(-1, 2)  # seek to last byte
            _needs_newline = _f.read(1) not in (b"\n", b"")
    except (FileNotFoundError, OSError):
        _needs_newline = False

    with open(ALERT_HISTORY_FILE, "a") as f:
        if _needs_newline:
            f.write("\n")
        f.write(json.dumps(record) + "\n")


def _build_wxo_log_entry(alert_data: dict, response: dict) -> dict:
    fields = extract_log_fields(alert_data, response)
    return {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        **fields,
    }


# ── Telemetry consumer — raw 5-second ticks from env_sensor_data ─────────────
# Runs in a daemon thread so it doesn't block the main alert loop.
# Uses a separate consumer group so it never interferes with Flink offsets.
def _telemetry_consumer_loop() -> None:
    raw_conf = {
        'bootstrap.servers': 'localhost:9092',
        'group.id': 'wxo-telemetry-reader',
        'auto.offset.reset': 'latest',
        # Never commit offsets for this stateless reader — on every restart
        # it should start from the latest message, not a stale committed
        # offset that may no longer exist on the broker (causes the
        # "Offset out of range" error when the topic is reset or truncated).
        'enable.auto.commit': 'false',
    }
    raw_consumer = Consumer(raw_conf)
    raw_consumer.subscribe(['env_sensor_data'])
    print("📊 Telemetry consumer active — reading raw ticks from 'env_sensor_data'")
    try:
        while True:
            msg = raw_consumer.poll(timeout=1.0)
            if msg is None or msg.error():
                continue
            try:
                raw = json.loads(msg.value().decode('utf-8'))
                _append_sensor_log(raw)
            except Exception:
                pass
    finally:
        raw_consumer.close()


# Start the telemetry reader in the background before the main loop
_t = threading.Thread(target=_telemetry_consumer_loop, daemon=True)
_t.start()

# ── Main alert consumer — Flink aggregated alerts on sensor_alerts ────────────
consumer = Consumer(conf)
topic = 'sensor_alerts'
consumer.subscribe([topic])

print(f"🌉 Agent bridge active — wxo mode. Listening for Flink alerts on topic '{topic}'...")
print(f"⏱️  Alert cooldown: {COOLDOWN_SECONDS}s per sensor (override with ALERT_COOLDOWN_SECONDS env var)")

try:
    while True:
        msg = consumer.poll(timeout=1.0)

        if msg is None or msg.error():
            continue

        alert_data = json.loads(msg.value().decode('utf-8'))
        sensor_id  = alert_data.get("sensor_id", "UNKNOWN")

        if _is_suppressed(sensor_id):
            continue

        # Increment in-memory counter BEFORE calling the agent so the prompt
        # receives the correct prior count regardless of file-write timing.
        prior_count = _dispatch_count.get(sensor_id, 0)
        _dispatch_count[sensor_id] = prior_count + 1

        if _DEBUG_DUMP:
            from wxo_client import build_agent_prompt
            print("── PROMPT SENT ───────────────────────────────────────")
            print(repr(build_agent_prompt(alert_data, prior_dispatches=prior_count)))
            print("──────────────────────────────────────────────────────")
            sys.stdout.flush()

        response = invoke_wxo_agent(alert_data, prior_dispatches=prior_count)
        run_id = response.get("id", "UNKNOWN")
        log_entry = _build_wxo_log_entry(alert_data, response)
        _append_log(log_entry)
        # Pass alert_data (signals) and log_entry (resolved urgency/dept) separately —
        # never merge them so signal floats cannot be silently overwritten.
        _append_alert_history(alert_data, resolved=log_entry)
        print(f"✅ wxO agent workflow completed. Run ID: {run_id}")

        print("==================================================\n")

except KeyboardInterrupt:
    print("\nBridge shutting down...")
finally:
    consumer.close()
