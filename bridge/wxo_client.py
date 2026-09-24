import json
import os
import re
from urllib import error, request as urllib_request

# ---------------------------------------------------------------------------
# Configuration — read from environment at call time (not at import time)
# so that tokens rotated while the bridge is running are always picked up.
# WXO_BASE_URL and WXO_TIMEOUT_SECONDS are stable and safe to read once.
# ---------------------------------------------------------------------------
WXO_BASE_URL        = os.getenv("WXO_BASE_URL", "http://localhost:4321/api/v1")
WXO_TIMEOUT_SECONDS = float(os.getenv("WXO_TIMEOUT_SECONDS", "120"))

_DISPATCH_TAG = "DISPATCH_PAYLOAD::"


class WXOConfigurationError(RuntimeError):
    pass


class WXOInvocationError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_agent_prompt(alert_data: dict, prior_dispatches: int = 0) -> str:
    """Build the prompt sent to the wxO agent.

    Args:
        alert_data: Flink alert payload (sensor values, zone, sensor_id, timestamp).
        prior_dispatches: Number of dispatches already sent for this sensor in the
            current session (passed from the bridge's in-memory counter so the
            recurrence status is correct even before alert_history.json is flushed).
    """
    temp = alert_data.get('temperature_c', alert_data.get('current_value', 0))
    hum  = alert_data.get('humidity_pct', 50.0)
    co2  = alert_data.get('co2_ppm', 600.0)
    co   = alert_data.get('co_ppm', 5.0)
    pm25 = alert_data.get('pm25_ugm3', 10.0)
    timestamp = alert_data.get('timestamp', 'Unknown')
    sensor_id = alert_data.get('sensor_id', 'UNKNOWN')
    zone = alert_data.get('zone', 'UNKNOWN').replace('_', ' ')

    prior = prior_dispatches
    if prior == 0:
        recurrence_line = "RECURRENCE STATUS: First occurrence — no prior dispatches for this sensor."
    elif prior == 1:
        recurrence_line = (
            f"RECURRENCE STATUS: REPEAT — this sensor has already fired {prior} time before this dispatch. "
            f"DO NOT write 'first occurrence'. Call get_prior_dispatches to see what was recommended last time."
        )
    else:
        recurrence_line = (
            f"RECURRENCE STATUS: SUSTAINED — this sensor has already fired {prior} times before this dispatch. "
            f"DO NOT write 'first occurrence'. Prior actions have not resolved the condition. "
            f"Call get_prior_dispatches to review prior recommendations and ESCALATE accordingly."
        )

    return (
        f"{recurrence_line} "
        f"Zone: {zone} | Sensor ID: {sensor_id} | Timestamp: {timestamp} "
        f"Live sensor snapshot: "
        f"- Temperature : {temp:.2f} °C "
        f"- Humidity    : {hum:.2f} % "
        f"- CO₂         : {co2:.0f} ppm "
        f"- CO          : {co:.1f} ppm "
        f"- PM2.5       : {pm25:.1f} µg/m³"
    )


# ---------------------------------------------------------------------------
# Two-call strategy:
#   1. POST /orchestrate/{agent_id}/chat/completions  — gets final text + run_id
#   2. GET  /orchestrate/runs/{run_id}                — gets step_history with tool outputs
# ---------------------------------------------------------------------------

def _build_chat_url(agent_id: str) -> str:
    return f"{WXO_BASE_URL.rstrip('/')}/orchestrate/{agent_id}/chat/completions"


def _build_run_url(run_id: str) -> str:
    return f"{WXO_BASE_URL.rstrip('/')}/orchestrate/runs/{run_id}"


def _fetch_run(run_id: str, token: str, retries: int = 5, delay: float = 1.0) -> dict:
    """GET /orchestrate/runs/{run_id} and poll until step_history is non-empty."""
    import time
    for attempt in range(retries):
        req = urllib_request.Request(
            _build_run_url(run_id),
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        try:
            with urllib_request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except Exception:
            return {}

        # Check both known locations for step_history
        steps = (
            data.get("result", {}).get("data", {}).get("step_history")
            or data.get("step_history")
        )
        if steps:
            return data

        if attempt < retries - 1:
            time.sleep(delay)

    return data  # return whatever we got on the last attempt


def invoke_wxo_agent(alert_data: dict, thread_id: str | None = None, prior_dispatches: int = 0) -> dict:
    """Call the agent and return a combined response with final text + tool step history.

    Step 1: POST chat/completions → final_text + run_id (fast, reliable)
    Step 2: GET  /runs/{run_id}   → step_history with DISPATCH_PAYLOAD:: and env_report
    Returns a merged dict with both.

    WXO_AGENT_ID and WXO_BEARER_TOKEN are read fresh from the environment on every
    call so that a token rotated while the bridge is running is always picked up
    without restarting the process.
    """
    # Read credentials fresh on every invocation — not from module-level globals —
    # so a rotated bearer token is always honoured without a bridge restart.
    agent_id = os.getenv("WXO_AGENT_ID", "")
    token    = os.getenv("WXO_BEARER_TOKEN", "")

    if not agent_id:
        raise WXOConfigurationError("WXO_AGENT_ID is not set")
    if not token:
        raise WXOConfigurationError("WXO_BEARER_TOKEN is not set")

    body: dict = {
        "stream": False,
        "messages": [{"role": "user", "content": build_agent_prompt(alert_data, prior_dispatches=prior_dispatches)}],
    }
    if thread_id:
        body["thread_id"] = thread_id

    req = urllib_request.Request(
        _build_chat_url(agent_id),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        },
        method="POST",
    )

    try:
        with urllib_request.urlopen(req, timeout=WXO_TIMEOUT_SECONDS) as resp:
            chat_resp = json.loads(resp.read())
    except error.HTTPError as exc:
        body_txt = exc.read().decode("utf-8", errors="replace")
        raise WXOInvocationError(f"WXO returned HTTP {exc.code}: {body_txt}") from exc
    except error.URLError as exc:
        raise WXOInvocationError(f"WXO request failed: {exc.reason}") from exc

    # Step 2: fetch run detail for step_history (pass token for the same reason)
    run_id     = chat_resp.get("run_id", "")
    run_detail = _fetch_run(run_id, token) if run_id else {}

    # Merge: add step_history into the chat response for extract_log_fields
    chat_resp["_step_history"] = (
        run_detail.get("result", {}).get("data", {}).get("step_history")
        or run_detail.get("step_history")
        or []
    )

    if os.getenv("WXO_DEBUG_DUMP") == "1":
        import sys
        # Print only safe, non-sensitive fields — never dump the raw response
        # which may contain auth metadata, session IDs, or internal service data.
        safe = {
            "run_id":        chat_resp.get("run_id"),
            "model":         chat_resp.get("model"),
            "usage":         chat_resp.get("usage"),
            "choices_count": len(chat_resp.get("choices", [])),
            "step_count":    len(chat_resp.get("_step_history", [])),
        }
        print("── AGENT RESPONSE (safe fields only) ────────────────")
        print(json.dumps(safe, indent=2))
        print("──────────────────────────────────────────────────────")
        sys.stdout.flush()

    return chat_resp


# ---------------------------------------------------------------------------
# Field extraction from the chat/completions response
# ---------------------------------------------------------------------------

def _regex_extract(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1) if m else None


def _find_dispatch_in_steps(steps: list) -> dict | None:
    """Walk step_history tool outputs for a DISPATCH_PAYLOAD:: tagged result."""
    for step in steps:
        for tc in (step.get("tool_calls") or []):
            output = tc.get("output", "")
            if isinstance(output, str) and output.startswith(_DISPATCH_TAG):
                try:
                    return json.loads(output[len(_DISPATCH_TAG):])
                except json.JSONDecodeError:
                    pass
    return None


def _find_env_report_in_steps(steps: list) -> str:
    """Walk step_history for the check_zone_ambient_conditions output."""
    for step in steps:
        for tc in (step.get("tool_calls") or []):
            output = tc.get("output", "")
            if isinstance(output, str) and "Zone environmental report" in output:
                return output
    return ""


def extract_log_fields(alert_data: dict, response: dict) -> dict:
    """Extract dashboard log fields from the merged invoke_wxo_agent response.

    response shape (merged by invoke_wxo_agent):
      choices[0].message.content  – final assistant text  (from chat/completions)
      _step_history               – tool call steps       (from GET /runs/{run_id})
    """
    # Final assistant text
    final_text = ""
    choices = response.get("choices", [])
    if choices:
        content = choices[0].get("message", {}).get("content", "")
        if isinstance(content, str):
            final_text = content.strip()

    # Tool step history injected by invoke_wxo_agent from the run detail
    steps = response.get("_step_history") or []

    dispatch = _find_dispatch_in_steps(steps)
    env_report = _find_env_report_in_steps(steps)

    if dispatch:
        return {
            "sensor_id":  dispatch.get("sensor_id",  alert_data.get("sensor_id", "UNKNOWN")),
            "zone":       dispatch.get("zone",        alert_data.get("zone", "UNKNOWN")),
            "urgency":    dispatch.get("urgency",     "INFO").upper(),
            "department": dispatch.get("department",  "Facilities"),
            "message":    dispatch.get("message",     final_text),
            "reasoning":  final_text,
            "env_report": env_report,
        }

    # Fallback: regex parse the final text
    department = (
        _regex_extract(r"department\s*[:=-]\s*(EHS|Mechanics|Electrical|Facilities)", final_text)
        or _regex_extract(r"\b(EHS|Mechanics|Electrical|Facilities)\b", final_text)
        or "Facilities"
    )
    urgency = (
        _regex_extract(r"urgency\s*[:=-]\s*(CRITICAL|INFO)", final_text)
        or _regex_extract(r"\b(CRITICAL|INFO)\b", final_text)
        or "INFO"
    )
    scenario  = alert_data.get("simulated_scenario", "Unknown")
    zone      = alert_data.get("zone", "UNKNOWN")
    sensor_id = alert_data.get("sensor_id", "UNKNOWN")
    message   = final_text.strip() or f"{scenario} detected in {zone} (sensor {sensor_id})."
    return {
        "sensor_id":  sensor_id,
        "zone":       zone,
        "urgency":    urgency.upper(),
        "department": department,
        "message":    message,
        "reasoning":  final_text,
        "env_report": env_report,
    }
