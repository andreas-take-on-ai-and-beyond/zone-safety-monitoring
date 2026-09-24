import os
import time
import json
import random
from datetime import datetime
from confluent_kafka import Producer

# ── Zone Config ───────────────────────────────────────────────────────────────
# Zone: CNC Machining
# Risk profile: coolant leaks (humidity spike), bearing overheat (dry high temp),
#               metalworking dust (PM2.5), CO from coolant decomposition
# ENV_SENSOR_ZONE_CNC represents a per-zone environmental sensor suite:
#   • BME280           → temperature, pressure, humidity
#   • MQ-7 / electrochemical → CO (ppm)
#   • SDS011 / optical particle counter → PM2.5 (µg/m³)
#   • MH-Z19 / NDIR    → CO₂ (ppm)
# All readings are aggregated into a single payload per zone tick.
SENSOR_ID  = "ENV_SENSOR_ZONE_CNC"
KAFKA_KEY  = "sensor_cnc"
BASE_TEMP  = 26.0    # CNC zones run slightly warmer than ambient (24–28 °C midpoint)
BASE_PRESS = 1011.5  # slight negative pressure from LEV (local exhaust ventilation)
BASE_HUM   = 45.0    # moderate baseline — coolant mist keeps it mid-range
BASE_CO2   = 650     # elevated vs office — machinery + operators
BASE_CO    = 4.0     # low background trace — tramp oil / hydraulic heating
BASE_PM25  = 15.0    # metal dust + coolant aerosol permanently present (10–20 µg/m³)
TOPIC      = "env_sensor_data"

# ── Scenario selection ────────────────────────────────────────────────────────
# Set the SCENARIO environment variable before launching this script.
#
#   SCENARIO=NORMAL                  (default) — realistic shift baseline, no alarms
#   SCENARIO=TOOL_BINDING_FIRE       — tool dulls, coolant ignites → CRITICAL / EHS
#   SCENARIO=CHIP_BLOWOFF            — operator air-gun chip removal → benign spike
#   SCENARIO=COOLANT_LEAK            — coolant pipe bursts → humidity spike → Mechanics
#   SCENARIO=BEARING_OVERHEAT        — dry bearing friction → dry heat → Electrical
#
# Example:
#   SCENARIO=COOLANT_LEAK python sensor_cnc.py
# ─────────────────────────────────────────────────────────────────────────────
SCENARIO = os.getenv("SCENARIO", "NORMAL").upper().strip()
VALID_SCENARIOS = {"NORMAL", "TOOL_BINDING_FIRE", "CHIP_BLOWOFF", "COOLANT_LEAK", "BEARING_OVERHEAT"}
if SCENARIO not in VALID_SCENARIOS:
    print(f"⚠️  Unknown SCENARIO='{SCENARIO}'. Falling back to NORMAL.")
    SCENARIO = "NORMAL"

producer = Producer({'bootstrap.servers': 'localhost:9092'})

print(f"🚀 [{SENSOR_ID}] Sensor simulation started — CNC Machining Zone")
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
    temp  = round(_clamp(current_temp,  20.0, 55.0),  2)
    press = round(_clamp(current_press, 990.0, 1030.0), 2)
    hum   = round(_clamp(current_hum,   10.0, 95.0),  2)
    co2   = round(_clamp(current_co2,   400,  5000),   0)
    co    = round(_clamp(current_co,    0.0,  200.0),  1)
    pm25  = round(_clamp(current_pm25,  0.0,  500.0),  1)

    payload = {
        "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sensor_id":     SENSOR_ID,
        "zone":          "CNC_Machining",
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
    Realistic CNC shift baseline — all values stay well within safe thresholds.
    Sawtooth PM2.5 bumps when part-swap doors open; temperature varies gently
    through the batch cycle; CO and humidity remain flat and safe.
    No alerts, no warnings — everything is right.
    """
    global current_temp, current_press, current_hum, current_co2, current_co, current_pm25

    step  = 0
    phase = "run"   # phases: run → idle → run …  (12-min milling cycle approximation)
    idle_steps = 0

    try:
        while True:
            step += 1
            # Every 24 ticks (~2 min) toggle between run / idle
            if phase == "run" and step % 24 == 0:
                phase = "idle"
                idle_steps = 0
                print(f"\n⚙️  [{SENSOR_ID}] Batch cycle complete — machine idling…\n")
            elif phase == "idle":
                idle_steps += 1
                if idle_steps >= 6:   # idle for 6 ticks (~30 s)
                    phase = "run"
                    step  = 0
                    print(f"\n▶️  [{SENSOR_ID}] Next batch starting — spindle up…\n")

            if phase == "run":
                # Gentle temperature rise during cutting
                current_temp  += random.uniform(0.05, 0.20)
                current_temp   = _clamp(current_temp, BASE_TEMP - 1, BASE_TEMP + 2)
                # Humidity inversely tracks temperature — stays in safe range
                current_hum   += random.uniform(-0.3, 0.1)
                current_hum    = _clamp(current_hum, 40.0, 50.0)
                # PM2.5 sawtooth: small bump every 4 ticks (door opens for part swap)
                if step % 4 == 0:
                    current_pm25 += random.uniform(2.0, 5.0)
                else:
                    current_pm25 += (BASE_PM25 - current_pm25) * 0.3
                current_pm25 = _clamp(current_pm25, 10.0, 22.0)
            else:
                # Machine idle — everything drifts toward baseline
                current_temp  += (BASE_TEMP  - current_temp)  * 0.15
                current_hum   += (BASE_HUM   - current_hum)   * 0.15
                current_pm25  += (BASE_PM25  - current_pm25)  * 0.20

            # CO and CO₂ — stable throughout (safe zone)
            current_co   += random.uniform(-0.2, 0.2)
            current_co    = _clamp(current_co,  2.0, 6.0)
            current_co2  += random.uniform(-10, 15)
            current_co2   = _clamp(current_co2, 600, 750)
            current_press += random.uniform(-0.15, 0.05)   # slight negative (LEV)
            current_press  = _clamp(current_press, 1009.5, 1012.5)

            _publish(f"NORMAL/{phase.upper()}")
            time.sleep(5)

    except KeyboardInterrupt:
        print(f"\n[{SENSOR_ID}] Simulation stopped.")


# ── SCENARIO: TOOL_BINDING_FIRE ───────────────────────────────────────────────
def run_tool_binding_fire() -> None:
    """
    Scenario A — Tool dulls / coolant flow blocked.
    Friction heats the workpiece above 300 °C, vaporising cutting fluid and
    igniting oil mist.

    Sensor trail:
      PM2.5  15 → 65 µg/m³  within 10 s (thick oil smoke)
      CO      4 → 25 ppm    (incomplete oil combustion)
      Temp   26 → 42 °C     over 60 s (thermal mass delay)

    After the incident peak the scenario loops back to a brief normal baseline
    before repeating — so the demo keeps running without manual intervention.
    """
    global current_temp, current_press, current_hum, current_co2, current_co, current_pm25

    try:
        while True:
            # ── Pre-incident: 10 normal ticks (~50 s) ────────────────────────
            print(f"\n✅ [{SENSOR_ID}] [TOOL_BINDING_FIRE] Pre-incident baseline…\n")
            for _ in range(10):
                current_co   = _clamp(current_co   + random.uniform(-0.1, 0.1), 3.5, 4.5)
                current_pm25 = _clamp(current_pm25 + random.uniform(-0.5, 0.5), 13.0, 17.0)
                current_temp = _clamp(current_temp + random.uniform(-0.1, 0.1), 25.5, 26.5)
                current_hum  = _clamp(current_hum  + random.uniform(-0.2, 0.2), 43.0, 47.0)
                current_co2  = _clamp(current_co2  + random.uniform(-5,  10),   630,  680)
                _publish("PRE-INCIDENT/NORMAL")
                time.sleep(5)

            # ── Phase 1: Oil mist ignition — PM2.5 and CO explode (2 ticks) ─
            print(f"\n🔥 [{SENSOR_ID}] [TOOL_BINDING_FIRE] Tool binding detected — oil igniting!\n")
            for _ in range(2):
                current_pm25 += random.uniform(20.0, 25.0)   # 15 → ~65 µg/m³
                current_co   += random.uniform(8.0,  12.0)   # 4  → ~25 ppm
                current_temp += random.uniform(0.5,  1.5)    # thermal delay
                current_hum  += random.uniform(-1.0, -0.5)
                _publish("INCIDENT/IGNITION")
                time.sleep(5)

            # ── Phase 2: Sustained fire — temperature climbs steadily (8 ticks)
            print(f"\n🔥 [{SENSOR_ID}] [TOOL_BINDING_FIRE] Fire sustained — temperature rising!\n")
            for _ in range(8):
                current_temp += random.uniform(1.5,  2.5)    # 26 → 42 °C over ~60 s
                current_pm25 += random.uniform(-2.0, 3.0)    # stays elevated ~60–70
                current_co   += random.uniform(0.0,  1.5)    # stays elevated ~25+ ppm
                current_hum  -= random.uniform(0.5,  1.5)
                _publish("INCIDENT/FIRE-SUSTAINED")
                time.sleep(5)

            # ── Phase 3: Suppression / cooldown (12 ticks) ───────────────────
            print(f"\n🧯 [{SENSOR_ID}] [TOOL_BINDING_FIRE] Suppression active — cooling down…\n")
            for _ in range(12):
                current_temp  += (BASE_TEMP  - current_temp)  * 0.20
                current_pm25  += (BASE_PM25  - current_pm25)  * 0.25
                current_co    += (BASE_CO    - current_co)    * 0.35
                current_hum   += (BASE_HUM   - current_hum)   * 0.20
                current_co2   += (BASE_CO2   - current_co2)   * 0.30
                _publish("RECOVERY/COOLDOWN")
                time.sleep(5)

    except KeyboardInterrupt:
        print(f"\n[{SENSOR_ID}] Simulation stopped.")


# ── SCENARIO: CHIP_BLOWOFF ────────────────────────────────────────────────────
def run_chip_blowoff() -> None:
    """
    Scenario B — Operator uses compressed air gun to blow metal chips off the part.

    Sensor trail:
      PM2.5  sharp spike to ~40 µg/m³ for 5 s then immediately back to baseline
      Temp, CO, Humidity — no change at all

    Demo value: shows how an intelligent agent IGNORES a brief particle spike
    when CO and temperature remain flat (false-alarm discrimination).
    """
    global current_temp, current_press, current_hum, current_co2, current_co, current_pm25

    try:
        while True:
            # ── Normal operation: 12 ticks (~60 s) ───────────────────────────
            print(f"\n✅ [{SENSOR_ID}] [CHIP_BLOWOFF] Normal operation before air-gun event…\n")
            for _ in range(12):
                current_co   = _clamp(current_co   + random.uniform(-0.1, 0.1), 3.5, 4.5)
                current_pm25 = _clamp(current_pm25 + random.uniform(-0.5, 0.5), 13.0, 17.0)
                current_temp = _clamp(current_temp + random.uniform(-0.1, 0.1), 25.5, 26.5)
                current_hum  = _clamp(current_hum  + random.uniform(-0.2, 0.2), 43.0, 47.0)
                current_co2  = _clamp(current_co2  + random.uniform(-5,  10),   630,  680)
                _publish("NORMAL/OPERATION")
                time.sleep(5)

            # ── Spike: 1 tick — compressed air gun fires ──────────────────────
            print(f"\n💨 [{SENSOR_ID}] [CHIP_BLOWOFF] Operator air gun — brief PM2.5 spike!\n")
            current_pm25 = 40.0 + random.uniform(-2.0, 2.0)   # sharp spike
            # CO, temp, humidity intentionally unchanged
            _publish("SPIKE/AIR-GUN")
            time.sleep(5)

            # ── Immediate drop back (1 tick) ──────────────────────────────────
            current_pm25 = BASE_PM25 + random.uniform(-1.0, 1.0)
            _publish("RECOVERY/NORMAL")
            time.sleep(5)

    except KeyboardInterrupt:
        print(f"\n[{SENSOR_ID}] Simulation stopped.")


# ── SCENARIO: COOLANT_LEAK ────────────────────────────────────────────────────
def run_coolant_leak() -> None:
    """
    Scenario C — Coolant supply pipe bursts or coupling fails.
    High-pressure coolant floods the enclosure floor and flashes into steam
    on hot machine surfaces.  Humidity explodes upward while temperature also
    rises from residual spindle heat.  CO stays low — no combustion.

    Agent routing: Mechanics (humidity > 60 % + elevated temperature).

    Sensor trail:
      Humidity  45 % → 75 %+  within 60 s (coolant mist and steam)
      Temp      26 °C → 40 °C  (residual spindle heat + steam flash)
      CO        flat (~4 ppm) — no combustion
      PM2.5     moderate rise (~25 µg/m³) — coolant aerosol
    """
    global current_temp, current_press, current_hum, current_co2, current_co, current_pm25

    try:
        while True:
            # ── Pre-incident: 10 normal ticks (~50 s) ────────────────────────
            print(f"\n✅ [{SENSOR_ID}] [COOLANT_LEAK] Normal machining operation…\n")
            for _ in range(10):
                current_temp  = _clamp(current_temp  + random.uniform(-0.1, 0.1), 25.5, 26.5)
                current_hum   = _clamp(current_hum   + random.uniform(-0.2, 0.2), 43.0, 47.0)
                current_co    = _clamp(current_co    + random.uniform(-0.1, 0.1),  3.5,  4.5)
                current_pm25  = _clamp(current_pm25  + random.uniform(-0.5, 0.5), 13.0, 17.0)
                current_co2   = _clamp(current_co2   + random.uniform(-5,   10),  630,  680)
                _publish("PRE-INCIDENT/NORMAL")
                time.sleep(5)

            # ── Phase 1: Pipe bursts — humidity surges, temp/PM25 spike (12 ticks)
            # Physics: high-pressure pipe burst is INSTANTANEOUS — coolant floods
            # the floor and immediately flashes to steam on hot surfaces.
            # Flink 60-s avg gate: CNC temp > 38 °C  AND  PM2.5 > 35 µg/m³
            # Strategy: immediate jump on tick 0 so all 12 ticks average above gates.
            #   Temp jump: +14 °C on tick 0  → avg over 12 ≈ 26+(14+12*0.4)/2 = ~40 °C
            #   PM25 jump: +25 µg/m³ on tick 0 → avg over 12 ≈ 15+(25+12*0.6)/2 = ~38 µg/m³
            print(f"\n💧 [{SENSOR_ID}] [COOLANT_LEAK] Coolant pipe burst — humidity surging!\n")
            # Tick 0: instantaneous burst — temp spikes; humidity surges; PM2.5 moderate
            # PM2.5 is intentionally kept BELOW 35 µg/m³ avg:
            #   Coolant mist = large droplets (>10 µm) — a PM2.5 sensor barely registers them.
            #   Combustion smoke = fine particles (0.1–1 µm) — that's what crosses 35 µg/m³.
            #   Keeping PM2.5 below the 35 gate means the agent routes via Mechanics
            #   (humidity surge + high temp) instead of misrouting to EHS (fire path).
            current_temp += random.uniform(13.0, 15.0)  # 26 → ~40 °C instantly (steam flash)
            current_pm25 += random.uniform(6.0,   10.0) # 15 → ~23 µg/m³ (coolant aerosol, NOT smoke)
            current_hum  += random.uniform(8.0,   12.0) # 45 % → ~55 % first tick
            current_co    = _clamp(current_co + random.uniform(-0.1, 0.1), 3.5, 4.5)
            current_co2   = _clamp(current_co2 + random.uniform(5, 15), 640, 720)
            _publish("INCIDENT/COOLANT-FLOODING")
            time.sleep(5)
            for _ in range(11):
                current_hum  += random.uniform(2.0, 3.5)   # 45+12 → ~75 %+ over 60 s
                current_temp += random.uniform(0.2, 0.6)   # stay elevated, slight further rise
                current_pm25 += random.uniform(0.3, 0.7)   # slight drift — stays below 35 avg
                # CO stays flat — no combustion; key discriminator vs TOOL_BINDING_FIRE
                current_co    = _clamp(current_co + random.uniform(-0.1, 0.1), 3.5, 4.5)
                current_co2   = _clamp(current_co2 + random.uniform(5,  15),   640, 720)
                _publish("INCIDENT/COOLANT-FLOODING")
                time.sleep(5)

            # ── Phase 2: Mechanics shuts off coolant valve — draining (10 ticks)
            print(f"\n🔧 [{SENSOR_ID}] [COOLANT_LEAK] Coolant valve closed — humidity draining…\n")
            for _ in range(10):
                current_hum  += (BASE_HUM  - current_hum)  * 0.20
                current_temp += (BASE_TEMP - current_temp) * 0.15
                current_pm25 += (BASE_PM25 - current_pm25) * 0.20
                _publish("RECOVERY/DRAINING")
                time.sleep(5)

    except KeyboardInterrupt:
        print(f"\n[{SENSOR_ID}] Simulation stopped.")


# ── SCENARIO: BEARING_OVERHEAT ────────────────────────────────────────────────
def run_bearing_overheat() -> None:
    """
    Scenario D — Spindle or axis bearing runs dry (lubrication failure).
    Metal-on-metal friction generates intense dry heat.  Humidity drops as the
    bearing housing heats up and desiccates the local air.  No coolant → no steam,
    no CO from combustion — just intense localised thermal energy.

    Agent routing: Electrical (humidity < 35 % + elevated temperature).

    Sensor trail:
      Temp      26 °C → 41 °C  (sustained bearing friction heat)
      Humidity  45 % → 28 %    (dry heat desiccates local air)
      CO        slight rise to ~8 ppm (bearing grease starts to off-gas)
      PM2.5     moderate (~20–28 µg/m³) — metal wear particles
    """
    global current_temp, current_press, current_hum, current_co2, current_co, current_pm25

    try:
        while True:
            # ── Pre-incident: 10 normal ticks (~50 s) ────────────────────────
            print(f"\n✅ [{SENSOR_ID}] [BEARING_OVERHEAT] Normal machining operation…\n")
            for _ in range(10):
                current_temp  = _clamp(current_temp  + random.uniform(-0.1, 0.1), 25.5, 26.5)
                current_hum   = _clamp(current_hum   + random.uniform(-0.2, 0.2), 43.0, 47.0)
                current_co    = _clamp(current_co    + random.uniform(-0.1, 0.1),  3.5,  4.5)
                current_pm25  = _clamp(current_pm25  + random.uniform(-0.5, 0.5), 13.0, 17.0)
                current_co2   = _clamp(current_co2   + random.uniform(-5,   10),  630,  680)
                _publish("PRE-INCIDENT/NORMAL")
                time.sleep(5)

            # ── Phase 1: Bearing runs dry — temp spikes hard, humidity falls (12 ticks)
            # Physics: a dry bearing seizes quickly — friction heat builds in seconds,
            # not minutes. The thermal spike is fast and sustained.
            # Flink 60-s avg gate: CNC temp > 38 °C
            # Strategy: immediate jump on tick 0 so the full 12-tick avg stays above 38.
            #   Temp jump: +15 °C on tick 0 → avg ≈ 26+(15+11*0.4)/2 = ~39 °C
            # CO intentionally stays below 15 ppm — grease off-gas only, routes to Electrical.
            print(f"\n🔥 [{SENSOR_ID}] [BEARING_OVERHEAT] Bearing lubrication failure — dry heat building!\n")
            # Tick 0: bearing seizes — immediate thermal spike
            current_temp += random.uniform(14.0, 16.0)  # 26 → ~41 °C instantly
            current_hum  -= random.uniform(3.0,  5.0)   # first tick humidity drop
            current_co   += random.uniform(0.5,  1.0)   # initial grease off-gas burst
            current_pm25 += random.uniform(2.0,  4.0)   # initial metal particle release
            current_co2   = _clamp(current_co2 + random.uniform(5, 15), 640, 720)
            _publish("INCIDENT/BEARING-DRY-RUN")
            time.sleep(5)
            for _ in range(11):
                current_temp += random.uniform(0.2, 0.5)   # stay elevated, slight further rise
                current_hum  -= random.uniform(0.8, 1.5)   # 45 → ~28 % (continued desiccation)
                current_co   += random.uniform(0.2, 0.4)   # grease off-gassing — stays ~6–10 ppm
                current_pm25 += random.uniform(0.3, 0.8)   # metal wear particles
                current_co2   = _clamp(current_co2 + random.uniform(5, 15), 640, 720)
                _publish("INCIDENT/BEARING-DRY-RUN")
                time.sleep(5)

            # ── Phase 2: Machine stopped — cooling (12 ticks) ─────────────────
            print(f"\n⏹  [{SENSOR_ID}] [BEARING_OVERHEAT] Machine halted — cooling down…\n")
            for _ in range(12):
                current_temp  += (BASE_TEMP - current_temp)  * 0.15
                current_hum   += (BASE_HUM  - current_hum)   * 0.15
                current_co    += (BASE_CO   - current_co)    * 0.30
                current_pm25  += (BASE_PM25 - current_pm25)  * 0.20
                _publish("RECOVERY/COOLING")
                time.sleep(5)

    except KeyboardInterrupt:
        print(f"\n[{SENSOR_ID}] Simulation stopped.")


# ── Entry point ───────────────────────────────────────────────────────────────
if SCENARIO == "TOOL_BINDING_FIRE":
    run_tool_binding_fire()
elif SCENARIO == "CHIP_BLOWOFF":
    run_chip_blowoff()
elif SCENARIO == "COOLANT_LEAK":
    run_coolant_leak()
elif SCENARIO == "BEARING_OVERHEAT":
    run_bearing_overheat()
else:
    run_normal()
