# Agent Output Examples

Reference outputs for all scenarios defined in `scenario_runner.sh`.
Sensor values are drawn from the mid-incident ranges in `sensor_cnc.py` and `sensor_assembly.py`.
All outputs reflect the current register (V5): one machine per zone, 1:1 sensor-to-machine mapping.

> **Consistency note:** Zone 1 contains exactly one machine — the Mazak VARIAXIS i-500.
> Zone 2 contains exactly one SMT line — DEK Horizon 03i → YSM20R → Heller 1809 MK5.
> Agent outputs name specific sub-components from the register where relevant.

---

## Scenario 1 — NORMAL / CNC (no dispatch)

**Sensor payload:**
```
Zone: CNC_Machining | Sensor ID: ENV_SENSOR_ZONE_CNC | Timestamp: 2025-07-28T08:05:12Z
- Temperature : 26.30 °C
- Humidity    : 44.80 %
- CO₂         : 668 ppm
- CO          :  4.20 ppm
- PM2.5       : 17.40 µg/m³
```

**Expected agent output:** No dispatch. No alert should be generated — all signals are within normal operating ranges for the CNC Machining zone. Temperature (26.3 °C) is within the 24–28 °C range, humidity (44.8 %) is within 40–50 %, CO (4.2 ppm) within 2–6 ppm, PM2.5 (17.4 µg/m³) within 10–20 µg/m³ (the sawtooth part-swap signature is expected during machining), and CO₂ (668 ppm) within 600–750 ppm. The VARIAXIS i-500 is running normally. No action required.

---

## Scenario 2 — TOOL_BINDING_FIRE (CNC, EHS CRITICAL)

**Sensor payload:**
```
Zone: CNC_Machining | Sensor ID: ENV_SENSOR_ZONE_CNC | Timestamp: 2025-07-28T10:14:32Z
- Temperature : 41.20 °C
- Humidity    : 31.00 %
- CO₂         : 710 ppm
- CO          : 27.50 ppm
- PM2.5       : 63.80 µg/m³
```

**Expected agent output:**

---

**CRITICAL — EHS**

Zone `ENV_SENSOR_ZONE_CNC` (CNC Machining, West Side) — Mazak VARIAXIS i-500 — is showing a tri-signal fire signature. CO at 27.50 ppm (+23.5 ppm above the 2–6 ppm baseline), PM2.5 at 63.80 µg/m³ (+48.8 µg/m³ above the 10–20 µg/m³ baseline), and zone temperature at 41.20 °C (+15.2 °C above the 26 °C baseline, +3.2 °C above the 38 °C critical threshold). Humidity has fallen to 31.00 % (−14 % below the 45 % baseline) from evaporative loss consistent with burning cutting fluid. CO₂ at 710 ppm is within the normal 600–750 ppm range and is not contributing.

The signal pattern is consistent with a tool-binding event on the VARIAXIS i-500: a dull or seized cutting tool generates sustained friction heat above the coolant flash point, vaporising water-miscible fluid and igniting accumulated oil mist in the enclosure `ENCL-CNC-01`. The high-pressure through-spindle coolant pump `PUMP-TSC-01` and flood coolant pump `PUMP-FLOOD-01` continue to feed fuel to the fire until isolated. CO (incomplete combustion of tramp oil), PM2.5 (oil smoke and carbonised coolant particles), and rising temperature form the classic tri-signal. This is the first recorded dispatch for this sensor.

Fire suppression hardware: fixed CO₂ system `SUPPRESS-CNC-01` (zone ceiling, full coverage; Kidde FM-200 backup); portables `EXT-CNC-W` (5 kg CO₂, EXIT-WEST) and `EXT-CNC-S` (5 kg CO₂, ENTRY-SOUTH). Zone coolant isolation: `VALVE-CNC-COOL-01` (red quarter-turn, north wall, adjacent to `TANK-CNC-COOL-01`). LEV boost available: `VFD-CNC-01` in panel `PLC-CNC-01` (north wall). Coolant chemistry in `TANK-CNC-COOL-01` is water-miscible emulsions — CO₂ / clean agent only, no water or foam.

EHS on-call: ext. 911 (internal) / 555-0199 (external).

---

**Sensor readings that triggered this alert:**

| Signal | Measured | Baseline | Deviation | Threshold |
| :--- | :--- | :--- | :--- | :--- |
| CO | 27.50 ppm | 4.0 ppm | +23.5 ppm | CRITICAL > 25 ppm |
| PM2.5 | 63.80 µg/m³ | 15.0 µg/m³ | +48.8 µg/m³ | WARNING > 35 µg/m³ (critical > 75 not yet reached) |
| Temperature | 41.20 °C | 26.0 °C | +15.2 °C | CRITICAL > 38 °C |
| Humidity | 31.00 % | 45.0 % | −14.0 % | Falling — evaporative loss from burning coolant |

CO₂ (710 ppm) within normal range — not contributing.

---

**Incident trajectory & recurrence:** ESCALATING — tri-signal simultaneous and rising. First occurrence for `ENV_SENSOR_ZONE_CNC`.

**Recommended immediate actions:**
1. Press E-stop `PANEL-OP-01` on the VARIAXIS i-500 immediately — halt spindle and all axis motion.
2. Activate fixed suppression `SUPPRESS-CNC-01`. Portable `EXT-CNC-W` (EXIT-WEST) or `EXT-CNC-S` (ENTRY-SOUTH) for local application — CO₂ only; water/foam prohibited due to coolant chemistry in `TANK-CNC-COOL-01`.
3. Close zone coolant isolation valve `VALVE-CNC-COOL-01` (red quarter-turn, north wall) to cut supply to both `PUMP-TSC-01` and `PUMP-FLOOD-01`.
4. Evacuate zone; contact EHS: ext. 911 / 555-0199.
5. After suppression confirmed: open enclosure door `DOOR-CNC-F` only when CO and temperature return toward baseline. Inspect spindle area and tool in `ATC-MAG-01` for binding marks, discolouration, or seized toolholder at HSK-A63 taper.

---

## Scenario 3 — CHIP_BLOWOFF (CNC, no dispatch — false-alarm discrimination)

**Sensor payload:**
```
Zone: CNC_Machining | Sensor ID: ENV_SENSOR_ZONE_CNC | Timestamp: 2025-07-28T11:02:44Z
- Temperature : 26.10 °C
- Humidity    : 44.60 %
- CO₂         : 651 ppm
- CO          :  4.10 ppm
- PM2.5       : 39.50 µg/m³
```

**Expected agent output:**

---

**No dispatch — benign transient**

Zone `ENV_SENSOR_ZONE_CNC` shows an isolated single-tick PM2.5 spike to 39.50 µg/m³ (+24.5 µg/m³ above the 15 µg/m³ baseline, crossing the 35 µg/m³ warning threshold). All other signals are completely flat: temperature 26.1 °C (normal), CO 4.1 ppm (normal baseline range), humidity 44.6 % (normal), CO₂ 651 ppm (normal). The spike is single-signal and instant.

The physical discriminator is decisive: in a genuine combustion or fire event on the VARIAXIS i-500, CO and temperature rise in parallel with PM2.5 — incomplete oil combustion produces CO and spindle friction raises ambient temperature simultaneously. Here CO is flat at 4.1 ppm (no combustion), temperature is flat at 26.1 °C (no thermal source), and the PM2.5 spike is transient. The pattern matches a mechanical disturbance — most likely an operator using a compressed-air gun to blow metal chips off the part or workholding after a tool change, ejecting a brief cloud of metal swarf and oil mist from the enclosure `ENCL-CNC-01` when the door `DOOR-CNC-F` opens. No structural failure, no fire precursor.

No action required. Continue monitoring. If PM2.5 remains above 35 µg/m³ into the next reading cycle, re-evaluate with the updated trajectory.

---

## Scenario 4 — COOLANT_LEAK (CNC, Mechanics CRITICAL)

**Sensor payload:**
```
Zone: CNC_Machining | Sensor ID: ENV_SENSOR_ZONE_CNC | Timestamp: 2025-07-28T13:28:17Z
- Temperature : 39.80 °C
- Humidity    : 74.20 %
- CO₂         : 695 ppm
- CO          :  4.30 ppm
- PM2.5       : 22.10 µg/m³
```

**Expected agent output:**

---

**CRITICAL — Mechanics**

Zone `ENV_SENSOR_ZONE_CNC` (CNC Machining, West Side) — Mazak VARIAXIS i-500 — is showing a high-humidity / high-temperature signature with flat CO. Humidity at 74.20 % is +29.2 % above the 45 % baseline and above the 70 % critical threshold. Temperature at 39.80 °C is +13.8 °C above baseline and +1.8 °C above the 38 °C critical threshold. CO at 4.30 ppm is within the normal 2–6 ppm range — flat. PM2.5 at 22.10 µg/m³ is a marginal rise above the 10–20 µg/m³ baseline, consistent with coolant aerosol (large droplets, not combustion smoke). CO₂ at 695 ppm is normal.

The critical discriminator: CO is flat. A fire or tool-binding event produces CO from incomplete combustion — CO rises in parallel with temperature. Here CO has not moved, eliminating combustion as the cause. The combination of explosive humidity rise and elevated temperature with flat CO is the characteristic signature of a coolant pipe burst on the VARIAXIS i-500: high-pressure coolant from `PUMP-TSC-01` (up to 70 bar, through-spindle) or `PUMP-FLOOD-01` has lost containment, flooding the enclosure floor and flashing to steam on hot machine surfaces. The machine-integrated coolant tank `TANK-INT-COOL-01` (under machine bed) feeds both pumps; the zone supply enters via `VALVE-CNC-COOL-01`. This is the first recorded dispatch for this sensor.

Coolant isolation: `VALVE-CNC-COOL-01` (red quarter-turn, north wall, adjacent to `TANK-CNC-COOL-01`). LEV: increase extraction via `VFD-CNC-01` at panel `PLC-CNC-01` (north wall) to clear steam. Mechanics on-call: ext. 2201.

---

**Sensor readings that triggered this alert:**

| Signal | Measured | Baseline | Deviation | Threshold |
| :--- | :--- | :--- | :--- | :--- |
| Humidity | 74.20 % | 45.0 % | +29.2 % | CRITICAL > 70 % |
| Temperature | 39.80 °C | 26.0 °C | +13.8 °C | CRITICAL > 38 °C |
| CO | 4.30 ppm | 4.0 ppm | +0.3 ppm | Normal — key discriminator (no combustion) |

PM2.5 (22.10 µg/m³) marginal rise — coolant aerosol, not smoke. CO₂ (695 ppm) normal.

---

**Incident trajectory & recurrence:** ESCALATING — humidity and temperature both rising simultaneously. First occurrence for `ENV_SENSOR_ZONE_CNC`.

**Recommended immediate actions:**
1. Press E-stop `PANEL-OP-01` on the VARIAXIS i-500 — halt all motion and spindle; stops `PUMP-TSC-01` and `PUMP-FLOOD-01` pump operation.
2. Close zone coolant isolation valve `VALVE-CNC-COOL-01` (red quarter-turn, north wall) immediately — cuts supply to `TANK-INT-COOL-01` and both pumps.
3. Increase LEV extraction via `VFD-CNC-01` at panel `PLC-CNC-01` to clear steam from the zone.
4. Once machine is stopped and coolant isolated, open enclosure door `DOOR-CNC-F` carefully — expect flooded floor. Locate the burst or failed coupling; inspect coolant nozzle manifold `MANIFOLD-COOL-01` and TSC hose connections at spindle bore for the leak point.
5. Contact Mechanics on-call: ext. 2201.

---

## Scenario 5 — BEARING_OVERHEAT (CNC, Electrical CRITICAL)

**Sensor payload:**
```
Zone: CNC_Machining | Sensor ID: ENV_SENSOR_ZONE_CNC | Timestamp: 2025-07-28T15:44:09Z
- Temperature : 40.60 °C
- Humidity    : 27.80 %
- CO₂         : 672 ppm
- CO          :  8.40 ppm
- PM2.5       : 23.50 µg/m³
```

**Expected agent output:**

---

**CRITICAL — Electrical**

Zone `ENV_SENSOR_ZONE_CNC` (CNC Machining, West Side) — Mazak VARIAXIS i-500 — is showing a dry-heat signature. Temperature at 40.60 °C (+14.6 °C above baseline, +2.6 °C above the 38 °C critical threshold). Humidity at 27.80 % (−17.2 % below the 45 % baseline) — critically low; the dry heat is desiccating the local air. CO at 8.40 ppm (+4.4 ppm above the 4.0 ppm baseline) — slightly elevated; consistent with grease or lubrication oil beginning to off-gas under heat, not active combustion. PM2.5 at 23.50 µg/m³ is a moderate rise above baseline — metal wear particles from friction, not oil smoke. CO₂ at 672 ppm is normal.

The discriminator pattern: temperature very high + humidity falling rapidly + CO only slightly elevated (not combustion levels) + no PM2.5 explosion. This is dry friction heat, not a fire. On the VARIAXIS i-500, the primary candidates are: spindle bearings `BRG-SPINDLE-U` / `BRG-SPINDLE-L` (ceramic angular contact, grease-lubricated, inside spindle head — primary heat source at high RPM, especially if grease has degraded or been contaminated by coolant entering via `ENC-SPINDLE-01`); or trunnion bearing housings `BRG-TRUNNION-L` / `BRG-TRUNNION-R` (large-diameter roller bearings at B-axis pivot points — susceptible during sustained tilt operations). The centralised lubrication unit `LUBE-CNC-01` should be checked for oil level and pump function — a starved ballscrew on `SCREW-X-01` / `SCREW-Y-01` / `SCREW-Z-01` is a secondary candidate if axis loads were high. The slightly elevated CO matches grease off-gassing from `BRG-SPINDLE-U/L` under thermal stress. This is the first recorded dispatch for this sensor.

Electrical cabinet `ELEC-CAB-CNC-01` (rear access panel) — verify no thermal alarm on spindle inverter `MTR-SPINDLE-01` or B/C-axis drives `MTR-B-AXIS-01` / `MTR-C-AXIS-01`. Electrical on-call: ext. 2202.

---

**Sensor readings that triggered this alert:**

| Signal | Measured | Baseline | Deviation | Threshold |
| :--- | :--- | :--- | :--- | :--- |
| Temperature | 40.60 °C | 26.0 °C | +14.6 °C | CRITICAL > 38 °C |
| Humidity | 27.80 % | 45.0 % | −17.2 % | CRITICAL < 30 % (dry desiccation) |
| CO | 8.40 ppm | 4.0 ppm | +4.4 ppm | Slightly elevated — grease off-gas, not combustion |

PM2.5 (23.50 µg/m³) moderate — metal wear particles. CO₂ (672 ppm) normal.

---

**Incident trajectory & recurrence:** ESCALATING — temperature rising, humidity falling. Dry bearing failure is progressive; without intervention bearing seizure and shaft damage follow. First occurrence for `ENV_SENSOR_ZONE_CNC`.

**Recommended immediate actions:**
1. Press E-stop `PANEL-OP-01` — halt spindle and all motion immediately; removes friction heat source.
2. Check `ELEC-CAB-CNC-01` (rear panel) for any drive fault or thermal alarm on spindle inverter and axis drive modules.
3. Check lubrication unit `LUBE-CNC-01` (left side of machine base): oil level in reservoir and pump operation indicator. A dry lubrication event affects all ballscrews simultaneously.
4. Once stopped and cooled, inspect spindle head: check temperature of spindle housing around `BRG-SPINDLE-U` / `BRG-SPINDLE-L` by touch or thermal gun. Inspect B-axis pivot housings `BRG-TRUNNION-L` / `BRG-TRUNNION-R` for discolouration or excess heat.
5. Contact Electrical on-call: ext. 2202. Contact Mechanics on-call (ext. 2201) for bearing and lubrication inspection once electrical faults are cleared.

---

## Scenario 6 — NORMAL / Assembly (no dispatch)

**Sensor payload:**
```
Zone: Electronics_Assembly | Sensor ID: ENV_SENSOR_ZONE_ASSEMBLY | Timestamp: 2025-07-28T09:10:05Z
- Temperature : 21.05 °C
- Humidity    : 52.30 %
- CO₂         : 724 ppm
- CO          :  2.20 ppm
- PM2.5       :  5.10 µg/m³
```

**Expected agent output:** No dispatch. All signals are within normal operating ranges for the Electronics Assembly zone. Temperature (21.05 °C) is within 20.5–21.5 °C (HVAC holding tight), humidity (52.3 %) is within the ESD-safe 50–55 % window with `HUM-ASSEMBLY-01` (Condair CP3) functioning correctly, CO (2.2 ppm) within 1.5–3 ppm baseline (consistent with reflow oven `BLOWER-REFLOW-01` background and idle solder iron trace), PM2.5 (5.1 µg/m³) near baseline 5 µg/m³ (fume extractor `FUME-EXT-PRINTER` running, reflow exhaust ducted via `DUCT-REFLOW-01`), CO₂ (724 ppm) within 500–900 ppm occupancy range. SMT line running normally. No action required.

---

## Scenario 7 — FUME_EXTRACTOR_FAILURE (Assembly, EHS CRITICAL)

**Sensor payload:**
```
Zone: Electronics_Assembly | Sensor ID: ENV_SENSOR_ZONE_ASSEMBLY | Timestamp: 2025-07-28T11:38:51Z
- Temperature : 21.10 °C
- Humidity    : 52.10 %
- CO₂         : 731 ppm
- CO          : 17.80 ppm
- PM2.5       : 44.20 µg/m³
```

**Expected agent output:**

---

**CRITICAL — EHS**

Zone `ENV_SENSOR_ZONE_ASSEMBLY` (Electronics Assembly, East Side) — SMT line — is showing an isolated fume accumulation signature. PM2.5 at 44.20 µg/m³ (+39.2 µg/m³ above the 5 µg/m³ baseline, above the 35 µg/m³ warning threshold). CO at 17.80 ppm (+15.8 ppm above the 2.0 ppm baseline, above the 10 ppm warning threshold). Temperature at 21.10 °C is completely flat — within the 20.5–21.5 °C normal range. Humidity at 52.10 % is normal. CO₂ at 731 ppm is normal.

The critical discriminator: temperature is flat at 21.1 °C. A reflow oven failure (`ZONE-REFLOW-01` to `ZONE-REFLOW-09` overheating) or any combustion event would raise zone temperature. Flat temperature with simultaneous CO and PM2.5 elevation is the signature of unextracted solder flux fumes — rosin/colophony from the solder paste `PASTE-DEK-01` on the DEK Horizon 03i or from reflow oven exhaust `BLOWER-REFLOW-01` bypassing the extraction path. The most likely cause is a duct disconnection or blockage in the zone fume extraction: paste printer extractor `FUME-EXT-PRINTER` (Weller Zero-Smog TL, above the DEK Horizon 03i, ducted to `DUCT-NORTH-E`), or the reflow oven exhaust duct connection `DUCT-REFLOW-01` (north wall, above the Heller 1809 MK5, connects `BLOWER-REFLOW-01` to `DUCT-NORTH-E`). A failed `BLOWER-REFLOW-01` would allow oven exhaust to recirculate into the zone rather than exhaust. This is the first recorded dispatch for this sensor.

Rosin flux fumes contain colophony, a known IgE sensitiser — prolonged exposure without extraction is a respiratory health risk. Evacuation threshold: CO > 25 ppm. Current level (17.8 ppm) is below evacuation threshold but approaching it; halt all soldering and reflow activity now. Fine water mist suppression `SUPPRESS-ASSY-01` is not applicable here (no fire). EHS on-call: ext. 911 / 555-0199.

---

**Sensor readings that triggered this alert:**

| Signal | Measured | Baseline | Deviation | Threshold |
| :--- | :--- | :--- | :--- | :--- |
| PM2.5 | 44.20 µg/m³ | 5.0 µg/m³ | +39.2 µg/m³ | WARNING > 35 µg/m³ |
| CO | 17.80 ppm | 2.0 ppm | +15.8 ppm | WARNING > 10 ppm |
| Temperature | 21.10 °C | 21.0 °C | +0.1 °C | Normal — key discriminator (no thermal event) |

Humidity (52.1 %), CO₂ (731 ppm) within normal range.

---

**Incident trajectory & recurrence:** ESCALATING — CO and PM2.5 both rising with flat temperature. First occurrence for `ENV_SENSOR_ZONE_ASSEMBLY`.

**Recommended immediate actions:**
1. Halt all reflow processing — stop the Heller 1809 MK5 conveyor `MTR-REFLOW-CONV` to stop boards entering the oven. Stop paste printing on the DEK Horizon 03i.
2. Check reflow oven exhaust: verify `BLOWER-REFLOW-01` (top of oven) is running and `DUCT-REFLOW-01` duct connection (north wall, above oven) is intact and seated.
3. Check paste printer extractor `FUME-EXT-PRINTER` (Weller Zero-Smog TL, above DEK Horizon 03i): verify duct connection to `DUCT-NORTH-E` is attached and filter is not saturated.
4. Open emergency exit `EXIT-EAST` for natural ventilation if CO approaches 25 ppm.
5. Contact EHS on-call: ext. 911 / 555-0199. If CO exceeds 25 ppm, evacuate zone immediately.

---

## Scenario 8 — HVAC_HUMIDIFIER_FAILURE (Assembly, Facilities INFO)

**Sensor payload:**
```
Zone: Electronics_Assembly | Sensor ID: ENV_SENSOR_ZONE_ASSEMBLY | Timestamp: 2025-07-28T14:07:55Z
- Temperature : 21.10 °C
- Humidity    : 22.40 %
- CO₂         : 718 ppm
- CO          :  2.10 ppm
- PM2.5       :  5.20 µg/m³
```

**Expected agent output:**

---

**INFO — Facilities**

Zone `ENV_SENSOR_ZONE_ASSEMBLY` (Electronics Assembly, East Side) — SMT line — is showing an isolated humidity collapse. Relative humidity at 22.40 % is −29.6 % below the 52 % baseline and below the 20 % critical lower threshold. All other signals are within normal ranges: temperature 21.10 °C (normal, HVAC air supply still functioning), CO 2.10 ppm (normal), PM2.5 5.20 µg/m³ (normal — reflow extraction `BLOWER-REFLOW-01` and `FUME-EXT-PRINTER` operating), CO₂ 718 ppm (normal).

The single-signal isolation — only humidity deviant, everything else flat including temperature — is the characteristic signature of a humidifier failure rather than an HVAC airflow loss (which would raise CO₂ and temperature) or a combustion event (which would raise CO and PM2.5). The integrated steam humidifier `HUM-ASSEMBLY-01` (Condair CP3) inside `AHU-ASSEMBLY-01` maintains the zone at 52 % RH setpoint. When it stops, dry supply air from `DUCT-NORTH-E` flushes residual moisture from the zone volume rapidly — typical drop of 25–30 percentage points within one 60-second Flink window, as observed here.

At 22.40 % RH, the ESD flooring system `ESD-FLOOR-ZONE2` (full zone floor area) has dropped below the 30 % minimum RH required for effective conductivity. The YSM20R pick-and-place gantry heads `HEAD-YSM-01` / `HEAD-YSM-02` handling bare PCBs are presenting components to discharge risk. ESD wrist-strap tester `ESD-TEST-01` (zone entrance, south side) should be used to assess any boards already placed since the humidity dropped. Humidifier electrical supply: breaker **CB-14**, Electrical Room E2. BMS interface: terminal `BMS-T3`, Control Room 104. This is the first recorded dispatch for this sensor. Facilities on-call: ext. 2203.

---

**Sensor readings that triggered this alert:**

| Signal | Measured | Baseline | Deviation | Threshold |
| :--- | :--- | :--- | :--- | :--- |
| Relative humidity | 22.40 % | 52.0 % | −29.6 % | CRITICAL < 20 % |

Temperature (21.10 °C), CO (2.10 ppm), PM2.5 (5.20 µg/m³), CO₂ (718 ppm) all normal — not contributing.

---

**Incident trajectory & recurrence:** SUSTAINED LOW — humidity collapsed in a single drop and is holding below the critical threshold. No other signal has moved. First occurrence for `ENV_SENSOR_ZONE_ASSEMBLY`.

**Recommended immediate actions:**
1. Stop the YSM20R pick-and-place (`HEAD-YSM-01` / `HEAD-YSM-02`) and halt all PCB handling — ESD floor threshold breached, `ESD-FLOOR-ZONE2` conductivity unreliable.
2. Check `HUM-ASSEMBLY-01` (Condair CP3) status via BMS terminal `BMS-T3`, Control Room 104.
3. Verify breaker **CB-14** (Electrical Room E2) is closed — if tripped, contact Electrical on-call (ext. 2202) before reset.
4. Contact Facilities on-call: ext. 2203.
5. Check `ESD-TEST-01` (zone entrance, south side) — test any boards handled since humidity dropped; quarantine boards with uncertain history.
6. Do not resume assembly until `ENV_SENSOR_ZONE_ASSEMBLY` reads ≥ 35 % RH sustained for 15 minutes.

---

## Scenario 9 — HVAC_BREAKDOWN (Assembly, Facilities CRITICAL)

**Sensor payload:**
```
Zone: Electronics_Assembly | Sensor ID: ENV_SENSOR_ZONE_ASSEMBLY | Timestamp: 2025-07-28T16:22:38Z
- Temperature : 27.40 °C
- Humidity    : 52.00 %
- CO₂         : 1 680 ppm
- CO          :  2.00 ppm
- PM2.5       :  5.00 µg/m³
```

**Expected agent output:**

---

**CRITICAL — Facilities**

Zone `ENV_SENSOR_ZONE_ASSEMBLY` (Electronics Assembly, East Side) — SMT line — is showing a ventilation failure signature. CO₂ at 1 680 ppm (+980 ppm above the 700 ppm baseline, above the 1 500 ppm critical threshold). Temperature at 27.40 °C (+6.4 °C above the 21 °C baseline, above the 26 °C critical threshold) — passive heat buildup from SMT line equipment and operators with no cooling airflow. Humidity at 52.0 % is normal — `HUM-ASSEMBLY-01` is not the cause. CO at 2.00 ppm is normal. PM2.5 at 5.00 µg/m³ is normal — no combustion or fume source.

The critical discriminator: CO and PM2.5 are completely flat. Any fire, fume extractor failure, or reflow exhaust bypass would elevate CO and/or PM2.5 first. Only CO₂ and temperature are rising, and humidity is unchanged. This is the unambiguous signature of a complete HVAC air supply failure: `AHU-ASSEMBLY-01` has stopped delivering fresh conditioned air. Without fresh-air dilution, operator exhalation (approximately 40 000 ppm CO₂ per breath) drives zone CO₂ upward at a rate directly proportional to the number of occupants. The temperature rise is passive — the Heller 1809 MK5 oven (typically 245–260 °C peak in the tunnel) and the YSM20R servo drives in `ELEC-CAB-YSM-01` continue generating heat with no cooling counterflow.

At 1 680 ppm CO₂, worker cognitive performance is measurably impaired. Above 2 000 ppm, evacuation risk increases. BMS terminal: `BMS-T3`, Control Room 104. AHU electrical feed status should be confirmed at `AHU-ASSEMBLY-01` (north wall / roof). HVAC contractor on-call: AirTech Services, 555-0142 (24 h). This is the first recorded dispatch for this sensor. Facilities on-call: ext. 2203.

---

**Sensor readings that triggered this alert:**

| Signal | Measured | Baseline | Deviation | Threshold |
| :--- | :--- | :--- | :--- | :--- |
| CO₂ | 1 680 ppm | 700 ppm | +980 ppm | CRITICAL > 1 500 ppm |
| Temperature | 27.40 °C | 21.0 °C | +6.4 °C | CRITICAL > 26 °C |
| CO | 2.00 ppm | 2.0 ppm | 0 ppm | Normal — key discriminator (no combustion) |

Humidity (52.0 %), PM2.5 (5.0 µg/m³) within normal range.

---

**Incident trajectory & recurrence:** ESCALATING — CO₂ and temperature both rising monotonically with no CO/PM2.5 movement. First occurrence for `ENV_SENSOR_ZONE_ASSEMBLY`.

**Recommended immediate actions:**
1. Check `AHU-ASSEMBLY-01` (north wall / roof) air supply status; confirm electrical feed is live and the unit has not tripped on a thermal or filter fault.
2. Check BMS terminal `BMS-T3` (Control Room 104) — confirm whether the AHU has faulted or been inadvertently shut down.
3. Open emergency exit `EXIT-EAST` immediately for natural ventilation — reduces CO₂ accumulation rate while AHU is offline.
4. If CO₂ exceeds 2 000 ppm: reduce occupancy in the zone; pause SMT line operation.
5. Contact Facilities on-call: ext. 2203. Contact HVAC contractor AirTech Services: 555-0142 (24 h) if AHU cannot be restored via BMS.
6. Note: the Heller 1809 MK5 oven (`ZONE-REFLOW-01` to `ZONE-REFLOW-09` at 245–260 °C) continues adding heat to the zone while running — consider pausing reflow processing to reduce thermal load while HVAC is offline.

---

## Scenario 0 — Both Zones NORMAL simultaneously (no dispatch)

**CNC payload:** Temperature 26.1 °C, Humidity 44.8 %, CO₂ 659 ppm, CO 4.1 ppm, PM2.5 16.2 µg/m³ — all within CNC normal ranges.
**Assembly payload:** Temperature 21.0 °C, Humidity 52.5 %, CO₂ 712 ppm, CO 2.1 ppm, PM2.5 5.0 µg/m³ — all within Assembly normal ranges.

**Expected agent output:** No dispatch for either zone. VARIAXIS i-500 and SMT line both running within normal envelope. No action required.

---

## Consistency Audit Notes

Cross-check of sensor code, zone baselines in `_ZONE_BASELINES`, zone thresholds in the register, and the scenarios above — findings:

| Check | Result |
| :--- | :--- |
| CNC baseline temp 26 °C: sensor `BASE_TEMP = 26.0`, tools `temp_baseline_c = 26.0`, register "24–28 °C" | ✅ Consistent |
| CNC baseline humidity 45 %: sensor `BASE_HUM = 45.0`, tools `hum_baseline_pct = 45.0`, register "40–50 %" | ✅ Consistent |
| CNC baseline CO 4 ppm: sensor `BASE_CO = 4.0`, tools `co_baseline_ppm = 4.0`, register "2–6 ppm" | ✅ Consistent |
| CNC baseline PM2.5 15 µg/m³: sensor `BASE_PM25 = 15.0`, tools `pm25_baseline_ugm3 = 15.0`, register "10–20 µg/m³" | ✅ Consistent |
| CNC baseline CO₂ 650 ppm: sensor `BASE_CO2 = 650`, tools `co2_baseline_ppm = 650.0`, register "600–750 ppm" | ✅ Consistent |
| Assembly baseline temp 21 °C: sensor `BASE_TEMP = 21.0`, tools `temp_baseline_c = 21.0`, register "20.5–21.5 °C" | ✅ Consistent |
| Assembly baseline humidity 52 %: sensor `BASE_HUM = 52.0`, tools `hum_baseline_pct = 52.0`, register "50–55 %" | ✅ Consistent |
| Assembly baseline CO 2 ppm: sensor `BASE_CO = 2.0`, tools `co_baseline_ppm = 2.0`, register "1.5–3 ppm" | ✅ Consistent |
| Assembly baseline PM2.5 5 µg/m³: sensor `BASE_PM25 = 5.0`, tools `pm25_baseline_ugm3 = 5.0`, register "3–8 µg/m³" | ✅ Consistent |
| Assembly baseline CO₂ 700 ppm: sensor `BASE_CO2 = 700`, tools `co2_baseline_ppm = 700.0`, register "500–900 ppm" | ✅ Consistent |
| COOLANT_LEAK: sensor drives humidity to ~75 %, register critical threshold > 70 % | ✅ Scenario crosses critical correctly |
| BEARING_OVERHEAT: sensor drives humidity to ~28 %, tools flag < 30 % as critically low | ✅ Crosses threshold correctly |
| HVAC_BREAKDOWN: sensor drives CO₂ to ~1 600 ppm, register critical > 1 500 ppm | ✅ Crosses critical correctly |
| FUME_EXTRACTOR_FAILURE: sensor drives PM2.5 to ~41 µg/m³, CO to ~17 ppm; register warning > 35 / > 10 | ✅ Both warning thresholds crossed, critical not yet reached — correct for WARNING level |
| HVAC_HUMIDIFIER_FAILURE: sensor drives humidity to ~22 %, register critical < 20 % | ⚠️ Sensor target ~22 % is above the 20 % critical boundary — dispatch level should be INFO/WARNING, not CRITICAL. Scenario is correctly labelled INFO in `scenario_runner.sh` |
| CHIP_BLOWOFF: sensor drives PM2.5 to ~40 µg/m³ for 1 tick, CO and temp flat | ✅ Single-tick single-signal — correct no-dispatch outcome |
| Scenario 2 example previously stated "specific machine cannot be identified" | ✅ Fixed — register now documents 1:1 zone-to-machine mapping; outputs name the VARIAXIS i-500 directly |
| Machine sub-components referenced in outputs vs register | ✅ All IDs used in outputs (BRG-SPINDLE-U/L, PUMP-TSC-01, BRG-TRUNNION-L/R, LUBE-CNC-01, HEAD-YSM-01/02, BLOWER-REFLOW-01, DUCT-REFLOW-01, ELEC-CAB-YSM-01) present in register |
| Assembly scenarios reference only zone-level hardware (BLOWER-REFLOW-01, FUME-EXT-PRINTER, DUCT-REFLOW-01) | ✅ All IDs present in register |
