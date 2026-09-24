import os
import time
import json
import random
from datetime import datetime
from confluent_kafka import Producer

# ── Zone Config ───────────────────────────────────────────────────────────────
# Zone: Electronics Assembly
# Risk profile: strict temperature (<28°C) and humidity (40-60%) for ESD protection,
#               soldering fumes (CO, PM2.5, VOC proxy via CO2), electrostatic risk
# ENV_SENSOR_ZONE_ASSEMBLY represents a per-zone environmental sensor suite:
#   • BME280           → temperature, pressure, humidity
#   • MQ-7 / electrochemical → CO (ppm)
#   • SDS011 / optical particle counter → PM2.5 (µg/m³)
#   • MH-Z19 / NDIR    → CO₂ (ppm)
# All readings are aggregated into a single payload per zone tick.
SENSOR_ID  = "ENV_SENSOR_ZONE_ASSEMBLY"
KAFKA_KEY  = "sensor_assembly"
BASE_TEMP  = 21.0    # tightly climate-controlled — electronics require cool ambient
BASE_PRESS = 1012.0
BASE_HUM   = 52.0    # kept in 50–55 % range; critical ESD window above 30 %
BASE_CO2   = 700     # elevated during working hours from operator occupancy
BASE_CO    = 2.0     # trace from soldering irons running; well below any threshold
BASE_PM25  = 5.0     # near-cleanroom air quality with benchtop fume extractors on
TOPIC      = "env_sensor_data"

# ── Scenario selection ────────────────────────────────────────────────────────
# Set the SCENARIO environment variable before launching this script.
#
#   SCENARIO=NORMAL                      (default) — stable shift baseline, no alarms
#   SCENARIO=FUME_EXTRACTOR_FAILURE      — benchtop extractor duct slips off → EHS
#   SCENARIO=HVAC_HUMIDIFIER_FAILURE     — HVAC humidifier fails → ESD / quality risk
#   SCENARIO=HVAC_BREAKDOWN              — HVAC air supply fails → CO₂ builds → Facilities
#
# Example:
#   SCENARIO=HVAC_BREAKDOWN python sensor_assembly.py
# ─────────────────────────────────────────────────────────────────────────────
SCENARIO = os.getenv("SCENARIO", "NORMAL").upper().strip()
VALID_SCENARIOS = {"NORMAL", "FUME_EXTRACTOR_FAILURE", "HVAC_HUMIDIFIER_FAILURE", "HVAC_BREAKDOWN"}
if SCENARIO not in VALID_SCENARIOS:
    print(f"⚠️  Unknown SCENARIO='{SCENARIO}'. Falling back to NORMAL.")
    SCENARIO = "NORMAL"

producer = Producer({'bootstrap.servers': 'localhost:9092'})

print(f"🚀 [{SENSOR_ID}] Sensor simulation started — Electronics Assembly Zone")
print(f"🎬 [{SENSOR_ID}] Active scenario: {SCENARIO}")
print()

# ── Shared running state ──────────────────────────────────────────────────────
current_temp  = BASE_TEMP
current_press = BASE_PRESS
current_hum   = BASE_HUM
current_co2   = float(BASE_CO2)
current_co    = float(BASE_CO)
current_pm25  = BASE_PM25


def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


def _publish(state_label: str) -> None:
    """Clamp, build payload, and publish the current sensor state to Kafka."""
    temp  = round(_clamp(current_temp,  18.0, 45.0),  2)
    press = round(_clamp(current_press, 990.0, 1030.0), 2)
    hum   = round(_clamp(current_hum,   10.0, 90.0),  2)
    co2   = round(_clamp(current_co2,   400,  5000),   0)
    co    = round(_clamp(current_co,    0.0,  200.0),  1)
    pm25  = round(_clamp(current_pm25,  0.0,  500.0),  1)

    payload = {
        "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sensor_id":     SENSOR_ID,
        "zone":          "Electronics_Assembly",
        "temperature_c": temp,
        "pressure_hpa":  press,
        "humidity_pct":  hum,
        "co2_ppm":       co2,
        "co_ppm":        co,
        "pm25_ugm3":     pm25,
        "current_value": temp,
    }

    producer.produce(TOPIC, key=KAFKA_KEY, value=json.dumps(payload))
    producer.flush()

    print(f"📡 [{SENSOR_ID}] [{state_label}] "
          f"Temp: {temp}°C | Hum: {hum}% | "
          f"CO₂: {co2}ppm | CO: {co}ppm | PM2.5: {pm25}µg/m³")


# ── SCENARIO: NORMAL ──────────────────────────────────────────────────────────
def run_normal() -> None:
    """
    Realistic electronics assembly shift baseline — all values tightly controlled.
    Temperature is extremely flat (HVAC fights any rise). CO₂ tracks human
    occupancy: rises gradually during working hours, dips at break/lunch.
    PM2.5 and CO near-zero throughout — fume extractors running correctly.
    No alerts, no warnings — everything is right.
    """
    global current_temp, current_press, current_hum, current_co2, current_co, current_pm25

    step = 0
    # Simulate an occupancy cycle: high_occupancy → break → high_occupancy …
    occupancy_phase = "high"
    phase_steps = 0

    try:
        while True:
            step += 1
            phase_steps += 1

            # Occupancy cycle: 30 ticks working (~2.5 min), 10 ticks on break
            if occupancy_phase == "high" and phase_steps >= 30:
                occupancy_phase = "break"
                phase_steps = 0
                print(f"\n☕ [{SENSOR_ID}] Shift break — operators step out, CO₂ drops…\n")
            elif occupancy_phase == "break" and phase_steps >= 10:
                occupancy_phase = "high"
                phase_steps = 0
                print(f"\n👷 [{SENSOR_ID}] Operators back at benches — CO₂ rises…\n")

            # Temperature: extremely flat — HVAC actively holds 21 °C
            current_temp += random.uniform(-0.05, 0.05)
            current_temp  = _clamp(current_temp, 20.5, 21.5)

            # Humidity: held in ESD-safe window
            current_hum  += random.uniform(-0.2, 0.2)
            current_hum   = _clamp(current_hum, 50.0, 55.0)

            # CO₂: correlates with occupancy
            if occupancy_phase == "high":
                current_co2 += random.uniform(5, 20)    # operators exhale
            else:
                current_co2 += random.uniform(-15, -5)  # air exchange clears it
            current_co2 = _clamp(current_co2, 500, 900)

            # CO and PM2.5: near-zero — fume extractors running
            current_co   += random.uniform(-0.1, 0.1)
            current_co    = _clamp(current_co,  1.5, 3.0)
            current_pm25 += random.uniform(-0.3, 0.3)
            current_pm25  = _clamp(current_pm25, 3.0, 8.0)

            current_press += random.uniform(-0.05, 0.05)
            current_press  = _clamp(current_press, 1011.5, 1012.5)

            _publish(f"NORMAL/{occupancy_phase.upper()}")
            time.sleep(5)

    except KeyboardInterrupt:
        print(f"\n[{SENSOR_ID}] Simulation stopped.")


# ── SCENARIO: FUME_EXTRACTOR_FAILURE ─────────────────────────────────────────
def run_fume_extractor_failure() -> None:
    """
    Scenario A — Benchtop fume extractor duct slips off during hand-soldering.
    Rosin-core flux fumes build gradually in the zone — health & EHS warning,
    NOT a fire. Temperature stays completely normal.

    Sensor trail:
      PM2.5  5 → 35 µg/m³  over 2–3 minutes (rosin particulate accumulation)
      CO     2 → 12 ppm    (burning flux)
      Temp   stays at 21 °C — no thermal event

    EHS action: inspect local soldering bench ventilation (no fire suppression).
    """
    global current_temp, current_press, current_hum, current_co2, current_co, current_pm25

    try:
        while True:
            # ── Pre-incident: 10 normal ticks (~50 s) ────────────────────────
            print(f"\n✅ [{SENSOR_ID}] [FUME_EXTRACTOR_FAILURE] Normal soldering operation…\n")
            for _ in range(10):
                current_temp  = _clamp(current_temp  + random.uniform(-0.05, 0.05), 20.8, 21.2)
                current_hum   = _clamp(current_hum   + random.uniform(-0.1,  0.1),  50.5, 53.5)
                current_co2   = _clamp(current_co2   + random.uniform(5,     15),   680,  730)
                current_co    = _clamp(current_co    + random.uniform(-0.1,  0.1),  1.8,  2.3)
                current_pm25  = _clamp(current_pm25  + random.uniform(-0.2,  0.2),  4.5,  5.5)
                _publish("PRE-INCIDENT/NORMAL")
                time.sleep(5)

            # ── Phase 1: Duct slips — fumes build quickly (12 ticks ~2 min)
            # Physics: when the local extractor fails, rosin flux fumes concentrate
            # immediately in the bench micro-environment then spread to the room sensor.
            # Flink 60-s avg gate: PM2.5 > 35 µg/m³  AND  CO > 15 ppm
            # Strategy: fast initial jump so both averages sit above their gates.
            #   PM25 jump: +32 µg/m³ tick 0 → avg ≈ 5+(32+11*1.5)/2 = ~27 µg/m³ — still short
            #   Better: jump to sustained high from tick 0.
            #   PM25: start at 40, drift +0.5-1.5 → avg ≈ 41 µg/m³ (> 35 ✓)
            #   CO:   start at 17, drift +0.3-0.8 → avg ≈ 19 ppm    (> 15 ✓)
            print(f"\n⚠️  [{SENSOR_ID}] [FUME_EXTRACTOR_FAILURE] Extractor duct dislodged — fumes accumulating!\n")
            # Jump to sustained fume level on tick 0 (duct slips → immediate local concentration)
            current_pm25 += random.uniform(30.0, 38.0)  # 5 → ~38–43 µg/m³ immediately
            current_co   += random.uniform(12.0, 15.0)  # 2 → ~14–17 ppm immediately
            # Temp unchanged — no thermal event; discriminates flux fumes from a fire
            current_temp  = _clamp(current_temp + random.uniform(-0.05, 0.05), 20.8, 21.2)
            current_co2   = _clamp(current_co2  + random.uniform(5,     15),   680,  750)
            _publish("INCIDENT/FUMES-BUILDING")
            time.sleep(5)
            for _ in range(11):
                current_pm25 += random.uniform(0.5, 1.5)   # stay elevated + slight drift
                current_co   += random.uniform(0.3, 0.8)   # stay elevated + slight drift
                current_temp  = _clamp(current_temp + random.uniform(-0.05, 0.05), 20.8, 21.2)
                current_co2   = _clamp(current_co2  + random.uniform(5,     15),   680,  750)
                _publish("INCIDENT/FUMES-BUILDING")
                time.sleep(5)

            # ── Phase 2: Technician replaces duct — recovery (10 ticks) ──────
            print(f"\n🔧 [{SENSOR_ID}] [FUME_EXTRACTOR_FAILURE] Technician reconnected extractor — clearing…\n")
            for _ in range(10):
                current_pm25  += (BASE_PM25 - current_pm25) * 0.30
                current_co    += (BASE_CO   - current_co)   * 0.35
                current_temp   = _clamp(current_temp + random.uniform(-0.05, 0.05), 20.8, 21.2)
                _publish("RECOVERY/VENTILATING")
                time.sleep(5)

    except KeyboardInterrupt:
        print(f"\n[{SENSOR_ID}] Simulation stopped.")


# ── SCENARIO: HVAC_HUMIDIFIER_FAILURE ────────────────────────────────────────
def run_hvac_humidifier_failure() -> None:
    """
    Scenario B — Central HVAC humidifier fails (winter / dry weather).
    Humidity drops steadily below the ESD-safe floor of 30 %.
    Temperature and air quality remain completely unchanged.

    Sensor trail:
      Humidity  52 % → 22 %  over ~5 minutes (fast drain), then sustained ≤22 %
      Temp, CO, PM2.5 — no change at all

    Demo nuance: triggers an INFO / Quality/ESD alert via Facilities, NOT a fire alarm.
    Sensitive IC assembly must pause before static charges damage components.

    Flink gate: Assembly humidity < 30 % average over a 60-second window.
    Strategy: fast drop to ~22 % in 12 ticks so the 60-s window average is ~26 %
    (< 30 %), then hold at ~22 % for 12 more ticks so the second window also fires.
    """
    global current_temp, current_press, current_hum, current_co2, current_co, current_pm25

    try:
        while True:
            # ── Pre-incident: 10 normal ticks (~50 s) ────────────────────────
            print(f"\n✅ [{SENSOR_ID}] [HVAC_HUMIDIFIER_FAILURE] Normal HVAC operation…\n")
            current_hum = _clamp(current_hum, 50.5, 53.5)   # reset to known good before each cycle
            for _ in range(10):
                current_temp  = _clamp(current_temp  + random.uniform(-0.05, 0.05), 20.8, 21.2)
                current_hum   = _clamp(current_hum   + random.uniform(-0.2,  0.2),  50.5, 53.5)
                current_co2   = _clamp(current_co2   + random.uniform(5,     15),   680,  730)
                current_co    = _clamp(current_co    + random.uniform(-0.1,  0.1),  1.8,  2.3)
                current_pm25  = _clamp(current_pm25  + random.uniform(-0.2,  0.2),  4.5,  5.5)
                _publish("PRE-INCIDENT/NORMAL")
                time.sleep(5)

            # ── Phase 1: Humidifier fails — humidity drops fast to ~22 % (12 ticks / 60 s) ─
            # Physics: without the humidifier, dry supply air flushes moisture quickly.
            # Flink 60-s avg gate: Assembly humidity < 30 %
            # Strategy: accelerated drop so the 12-tick avg is comfortably below 30 %.
            #   Starting at ~52 %, dropping ~2.5–3.5 %/tick:
            #   avg ≈ 52 - (0+1+2+…+11) × 3.0 / 12 ≈ 52 - 16.5 = ~35 % (marginal)
            #   Better: large jump on tick 0 forces early avg below 30 %.
            #   Tick 0: jump -25 % (52 → ~27); subsequent ticks drift -0.3 to -0.6.
            #   Avg ≈ (27 + 11×25) / 12 ≈ (27+275)/12 ≈ 25 % — well below 30 ✓
            print(f"\n❄️  [{SENSOR_ID}] [HVAC_HUMIDIFIER_FAILURE] Humidifier offline — humidity collapsing!\n")
            # Tick 0: rapid initial drop — humidifier stops, dry air floods the zone
            current_hum -= random.uniform(23.0, 27.0)   # 52 % → ~25–29 % immediately
            current_temp  = _clamp(current_temp  + random.uniform(-0.05, 0.05), 20.8, 21.2)
            current_co2   = _clamp(current_co2   + random.uniform(5,     15),   680,  750)
            current_co    = _clamp(current_co    + random.uniform(-0.1,  0.1),  1.8,  2.3)
            current_pm25  = _clamp(current_pm25  + random.uniform(-0.2,  0.2),  4.5,  5.5)
            _publish("INCIDENT/HUMIDITY-COLLAPSING")
            time.sleep(5)
            for _ in range(11):
                current_hum  -= random.uniform(0.3, 0.6)   # drift further down → ~22 %
                # Everything else stays perfectly normal — key discriminator vs BEARING_OVERHEAT
                current_temp  = _clamp(current_temp  + random.uniform(-0.05, 0.05), 20.8, 21.2)
                current_co2   = _clamp(current_co2   + random.uniform(5,     15),   680,  750)
                current_co    = _clamp(current_co    + random.uniform(-0.1,  0.1),  1.8,  2.3)
                current_pm25  = _clamp(current_pm25  + random.uniform(-0.2,  0.2),  4.5,  5.5)
                _publish("INCIDENT/HUMIDITY-COLLAPSING")
                time.sleep(5)

            # ── Phase 2: Hold at low humidity — second 60-s window also fires (12 ticks) ─
            print(f"\n⚠️  [{SENSOR_ID}] [HVAC_HUMIDIFIER_FAILURE] Humidity critically low — ESD floor breached!\n")
            for _ in range(12):
                current_hum   = _clamp(current_hum + random.uniform(-0.2, 0.2), 20.0, 24.0)
                current_temp  = _clamp(current_temp  + random.uniform(-0.05, 0.05), 20.8, 21.2)
                current_co2   = _clamp(current_co2   + random.uniform(5,     15),   680,  750)
                current_co    = _clamp(current_co    + random.uniform(-0.1,  0.1),  1.8,  2.3)
                current_pm25  = _clamp(current_pm25  + random.uniform(-0.2,  0.2),  4.5,  5.5)
                _publish("INCIDENT/ESD-FLOOR-BREACHED")
                time.sleep(5)

            # ── Phase 3: Facilities re-enables humidifier — humidity restores (10 ticks)
            print(f"\n🔧 [{SENSOR_ID}] [HVAC_HUMIDIFIER_FAILURE] Humidifier restored — humidity recovering…\n")
            for _ in range(10):
                current_hum  += (BASE_HUM - current_hum) * 0.35
                current_temp  = _clamp(current_temp + random.uniform(-0.05, 0.05), 20.8, 21.2)
                _publish("RECOVERY/HUMIDIFYING")
                time.sleep(5)

    except KeyboardInterrupt:
        print(f"\n[{SENSOR_ID}] Simulation stopped.")


# ── SCENARIO: HVAC_BREAKDOWN ──────────────────────────────────────────────────
def run_hvac_breakdown() -> None:
    """
    Scenario D — HVAC air-handling unit fails completely.
    Fresh-air supply stops; the zone becomes a closed volume.
    Operator exhalation drives CO₂ steadily upward.  Temperature creeps
    up slightly as cooling stops.  CO and PM2.5 remain flat because there
    is no combustion or particle source.

    Agent routing: Facilities (CO₂ > 1 400 ppm — ventilation failure, not EHS fire).

    Sensor trail:
      CO₂   700 ppm → 1 600+ ppm  over ~5 min (exhalation accumulation)
      Temp  21 °C   → 25 °C       (passive heat from occupants + equipment)
      Humidity  flat (~52 %)       (no HVAC change affecting moisture)
      CO        flat (~2 ppm)      — no combustion
      PM2.5     flat (~5 µg/m³)    — no new particle source
    """
    global current_temp, current_press, current_hum, current_co2, current_co, current_pm25

    try:
        while True:
            # ── Pre-incident: 10 normal ticks (~50 s) ────────────────────────
            print(f"\n✅ [{SENSOR_ID}] [HVAC_BREAKDOWN] Normal assembly operation…\n")
            for _ in range(10):
                current_temp  = _clamp(current_temp  + random.uniform(-0.05, 0.05), 20.8, 21.2)
                current_hum   = _clamp(current_hum   + random.uniform(-0.2,  0.2),  51.0, 53.0)
                current_co    = _clamp(current_co    + random.uniform(-0.1,  0.1),   1.8,  2.2)
                current_pm25  = _clamp(current_pm25  + random.uniform(-0.3,  0.3),   4.5,  5.5)
                current_co2   = _clamp(current_co2   + random.uniform(-10,   15),   680,  730)
                _publish("PRE-INCIDENT/NORMAL")
                time.sleep(5)

            # ── Phase 1: HVAC fails — CO₂ climbs, temp rises to above gate (15 ticks / 75 s)
            # Physics: without fresh-air dilution, operator exhalation raises CO₂ and the
            # zone warms passively from equipment + people. Heat rises monotonically.
            # Flink 60-s avg gate: Assembly temp > 26 °C
            # Strategy: fast initial rise so the 12-tick avg exceeds 26 °C.
            #   Temp jump: +6 °C on tick 0 → all subsequent ticks above 27 → avg ≈ 27–28 °C
            # CO and PM2.5 intentionally flat — Facilities dispatch, not EHS fire
            print(f"\n🌡️  [{SENSOR_ID}] [HVAC_BREAKDOWN] HVAC air supply offline — CO₂ building!\n")
            # Tick 0: HVAC stops — room begins heating immediately from equipment + occupants
            current_temp += random.uniform(5.5, 7.0)   # 21 → ~27–28 °C on first tick
            current_co2  += random.uniform(55, 80)
            current_co    = _clamp(current_co   + random.uniform(-0.05, 0.05), 1.8, 2.2)
            current_pm25  = _clamp(current_pm25 + random.uniform(-0.3,  0.3),  4.5, 5.5)
            current_hum   = _clamp(current_hum  + random.uniform(-0.1,  0.1), 50.5, 53.5)
            _publish("INCIDENT/HVAC-OFFLINE")
            time.sleep(5)
            for _ in range(14):
                current_co2  += random.uniform(55, 80)    # 700 → ~1 600 ppm over 15 ticks
                current_temp += random.uniform(0.10, 0.30)  # stay elevated, slight further rise
                # CO and PM2.5 stay flat — no combustion, no new particles
                current_co    = _clamp(current_co   + random.uniform(-0.05, 0.05), 1.8, 2.2)
                current_pm25  = _clamp(current_pm25 + random.uniform(-0.3,  0.3),  4.5, 5.5)
                current_hum   = _clamp(current_hum  + random.uniform(-0.1,  0.1), 50.5, 53.5)
                _publish("INCIDENT/HVAC-OFFLINE")
                time.sleep(5)

            # ── Phase 2: Facilities restores HVAC — CO₂ flushes out (12 ticks) ─
            print(f"\n🔧 [{SENSOR_ID}] [HVAC_BREAKDOWN] HVAC restored — flushing CO₂…\n")
            for _ in range(12):
                current_co2  += (float(BASE_CO2) - current_co2) * 0.25
                current_temp += (BASE_TEMP - current_temp) * 0.20
                _publish("RECOVERY/FLUSHING")
                time.sleep(5)

    except KeyboardInterrupt:
        print(f"\n[{SENSOR_ID}] Simulation stopped.")


# ── Entry point ───────────────────────────────────────────────────────────────
if SCENARIO == "FUME_EXTRACTOR_FAILURE":
    run_fume_extractor_failure()
elif SCENARIO == "HVAC_HUMIDIFIER_FAILURE":
    run_hvac_humidifier_failure()
elif SCENARIO == "HVAC_BREAKDOWN":
    run_hvac_breakdown()
else:
    run_normal()
