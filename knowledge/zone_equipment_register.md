# Zone-Level Equipment & Operational Register

* **Document ID:** REG-ZONE-AGG-2026-V5
* **Last Updated:** 2026-07-28
* **Maintained By:** Facilities, EHS, Mechanics & Electrical Teams
* **Primary Scope:** Main Industrial Hall — Zone-Level Aggregated View
* **Coverage:** Hall Infrastructure · Zone Conditions · Zone Hardware · Machine Sub-Components

> **Zone-to-machine mapping:** Each zone contains exactly one machine or line installation.
> The zone ambient sensor therefore maps 1:1 to that machine — sensor readings reflect
> the operating state of the single machine in that zone with no ambiguity.

---

## Hall Overview

The industrial hall is a single-storey building divided into two operational zones by a central full-height partition. A shared main corridor and entry runs along the south face. Emergency exits sit on the west (CNC side) and east (Assembly side) external walls. A continuous ventilation duct line runs along the full north wall, split into two independent spans — one per zone.

```
┌──────────────────────────────────┬──────────────────────────────────┐
│  [VENTILATION DUCT — WEST SPAN]  │  [VENTILATION DUCT — EAST SPAN]  │
│                                  │                                  │
│       CNC MACHINING ZONE         │    ELECTRONICS ASSEMBLY ZONE     │
│     Mazak VARIAXIS i-500         │  DEK Horizon 03i → YSM20R →      │
│       (5-axis mill-turn)         │     Heller 1809 MK5 SMT line     │
│                                  │                                  │
│   ENV_SENSOR_ZONE_CNC ●          │      ● ENV_SENSOR_ZONE_ASSEMBLY  │
│                                  │                                  │
[EXIT]                  ─ ─ ─ ─ ─ PARTITION ─ ─ ─ ─ ─                [EXIT]
│                                  │                                  │
└────────────────┬─────────────────┴────────────────┬────────────────┘
                 │              ENTRY                │
                 └─────────── MAIN CORRIDOR ─────────┘
```

### Hall-Level Fixed Infrastructure

| Item | ID / Label | Location | Owning Dept |
| :--- | :--- | :--- | :--- |
| North ventilation duct — west span | `DUCT-NORTH-W` | North wall above CNC zone | Facilities |
| North ventilation duct — east span | `DUCT-NORTH-E` | North wall above Assembly zone | Facilities |
| Central partition (full-height) | `PART-01` | Mid-hall, N–S axis | Facilities |
| Main corridor & hall entry | `ENTRY-SOUTH` | South face, centre | Facilities |
| West emergency exit | `EXIT-WEST` | West external wall | EHS / Facilities |
| East emergency exit | `EXIT-EAST` | East external wall | EHS / Facilities |
| Zone CNC ambient sensor | `ENV_SENSOR_ZONE_CNC` | Ceiling, CNC zone | Electrical / EHS |
| Zone Assembly ambient sensor | `ENV_SENSOR_ZONE_ASSEMBLY` | Ceiling, Assembly zone | Electrical / EHS |

### Departmental Scope (Hall-Wide)

| Department | Area of Ownership |
| :--- | :--- |
| **Mechanics** | Rotating machinery, coolant systems, LEV ductwork, mechanical isolation valves, spindle and axis lubrication |
| **Electrical** | PLC / CNC controller panels, servo drive cabinets, VFDs, breakers, environmental sensors, AHU electrical feeds |
| **EHS** | Fire suppression systems, extinguishers, evacuation routes, air quality monitoring, fume extraction systems |
| **Facilities** | HVAC / AHU operation, ductwork, building management system (BMS), partition & structural elements |

---

## Zone 1 — CNC Machining (`CNC_Machining`)

**Machine:** Mazak VARIAXIS i-500 — 5-axis vertical machining centre with mill-turn capability.
**Zone mapping:** this zone contains one machine. `ENV_SENSOR_ZONE_CNC` readings reflect the operating state of the VARIAXIS i-500 directly.

### Zone Profile

| Attribute | Detail |
| :--- | :--- |
| **Zone Sensor** | `ENV_SENSOR_ZONE_CNC` |
| **Hall Location** | West Side |
| **North boundary** | Exterior wall — ventilation duct `DUCT-NORTH-W` |
| **West boundary** | Emergency exit `EXIT-WEST` |
| **South boundary** | Main corridor & entry `ENTRY-SOUTH` |
| **East boundary** | Central partition `PART-01` |
| **Primary hazards** | Oil mist / coolant vapour, high thermal load from spindle and trunnion torque motors, metal dust (PM2.5), CO from coolant decomposition |

### Zone Ambient Thresholds (`ENV_SENSOR_ZONE_CNC`)

| Metric | Normal Range | Warning | Critical | Associated Risk |
| :--- | :--- | :--- | :--- | :--- |
| Ambient temperature | 24–28 °C | > 28 °C | > 38 °C | Thermal expansion on spindle and trunnion, coolant degradation |
| Relative humidity | 40–50 % | > 60 % | > 70 % | Coolant leak or steam ingress; condensation on axis guides and bearings |
| Carbon monoxide (CO) | 2–6 ppm | > 10 ppm | > 25 ppm | Coolant decomposition / tramp oil combustion |
| Particulates (PM2.5) | 10–20 µg/m³ | > 35 µg/m³ | > 75 µg/m³ | Metal dust or oil smoke |
| Carbon dioxide (CO₂) | 600–750 ppm | > 1 000 ppm | > 1 500 ppm | Ventilation failure |

---

### Zone Hardware Register

#### Ventilation & Air Quality

| Hardware Item | ID / Label | Location | Owning Dept | Notes |
| :--- | :--- | :--- | :--- | :--- |
| Local exhaust ventilation (LEV) fan unit | `LEV-CNC-01` | North wall, ducted to `DUCT-NORTH-W` | Mechanics / Facilities | VFD-driven; extracts oil mist and coolant vapour from the machine enclosure |
| LEV variable-frequency drive (VFD) | `VFD-CNC-01` | Inside `PLC-CNC-01` panel | Electrical | Controls speed of `LEV-CNC-01`; manual override switch on panel door |
| Zone PLC / control panel | `PLC-CNC-01` | North wall, CNC zone | Electrical | Hosts `VFD-CNC-01`; zone isolation controls |

#### Coolant Infrastructure

| Hardware Item | ID / Label | Location | Owning Dept | Notes |
| :--- | :--- | :--- | :--- | :--- |
| Zone coolant main isolation valve | `VALVE-CNC-COOL-01` | North wall, adjacent to coolant tank | Mechanics | Red manual quarter-turn valve |
| Bulk coolant storage tank | `TANK-CNC-COOL-01` | North wall alcove | Mechanics | Water-miscible emulsions and water-soluble synthetics |

#### Fire Suppression & Safety

| Hardware Item | ID / Label | Location | Owning Dept | Notes |
| :--- | :--- | :--- | :--- | :--- |
| Fixed gaseous suppression system | `SUPPRESS-CNC-01` | Zone ceiling, full coverage | EHS | CO₂ flood system; Kidde FM-200 backup agent |
| Portable CO₂ extinguisher | `EXT-CNC-W` | West exit `EXIT-WEST` | EHS | 5 kg CO₂ |
| Portable CO₂ extinguisher | `EXT-CNC-S` | South main entrance `ENTRY-SOUTH` | EHS | 5 kg CO₂ |

---

### Machine Sub-Components — Mazak VARIAXIS i-500

#### Spindle Assembly

| Component | ID / Label | Location on Machine | Owning Dept | Specification / Notes |
| :--- | :--- | :--- | :--- | :--- |
| Built-in motor spindle | `SPINDLE-CNC-01` | Spindle head, upper column | Mechanics / Electrical | Max 12 000 RPM; HSK-A63 taper interface; ceramic angular contact bearings |
| Spindle bearing set (upper + lower) | `BRG-SPINDLE-U` / `BRG-SPINDLE-L` | Inside spindle head housing | Mechanics | Ceramic angular contact; grease-lubricated; primary heat source at high RPM |
| Spindle motor & inverter | `MTR-SPINDLE-01` | Integrated in spindle head | Electrical | Built-in motor (no belt drive); inverter in electrical cabinet `ELEC-CAB-CNC-01` |
| Spindle encoder | `ENC-SPINDLE-01` | Rear spindle shaft | Electrical | Rotary encoder for position feedback; sensitive to coolant contamination |

#### 5-Axis Trunnion Table

| Component | ID / Label | Location on Machine | Owning Dept | Specification / Notes |
| :--- | :--- | :--- | :--- | :--- |
| Trunnion table assembly | `TABLE-CNC-01` | Machine bed, centre | Mechanics | Supports B-axis tilt (±110°) and C-axis rotation (360°) |
| B-axis torque motor | `MTR-B-AXIS-01` | Trunnion left pivot | Electrical | Direct-drive torque motor; no gearbox; heat source at sustained tilt operations |
| C-axis torque motor | `MTR-C-AXIS-01` | Trunnion table base | Electrical | Direct-drive torque motor; 360° continuous rotation |
| B/C-axis rotary encoders | `ENC-B-AXIS-01` / `ENC-C-AXIS-01` | Respective motor shafts | Electrical | High-resolution absolute encoders; seal condition critical |
| Trunnion bearing housings (×2) | `BRG-TRUNNION-L` / `BRG-TRUNNION-R` | Left and right pivot points | Mechanics | Large-diameter roller bearings; grease nipples on outer housing face |

#### Linear Axis Drives (X / Y / Z)

| Component | ID / Label | Location on Machine | Owning Dept | Specification / Notes |
| :--- | :--- | :--- | :--- | :--- |
| X-axis servo motor | `MTR-X-AXIS-01` | Column right side | Electrical | AC servo with ballscrew drive |
| Y-axis servo motor | `MTR-Y-AXIS-01` | Saddle rear | Electrical | AC servo with ballscrew drive |
| Z-axis servo motor | `MTR-Z-AXIS-01` | Column upper | Electrical | AC servo with ballscrew drive; gravity-loaded axis |
| Servo drive cabinet | `ELEC-CAB-CNC-01` | Rear of machine, external access panel | Electrical | Houses all axis drives, spindle inverter, and I/O modules; fan-cooled |
| Ballscrew assemblies (X/Y/Z) | `SCREW-X-01` / `SCREW-Y-01` / `SCREW-Z-01` | Respective axis ways | Mechanics | Preloaded double-nut; oil-lubricated via centralised lube unit `LUBE-CNC-01` |
| Centralised lubrication unit | `LUBE-CNC-01` | Left side of machine base | Mechanics | Automatic oil mist lubrication for all linear guides and ballscrews; reservoir on left panel |

#### Coolant System (Machine-Internal)

| Component | ID / Label | Location on Machine | Owning Dept | Specification / Notes |
| :--- | :--- | :--- | :--- | :--- |
| Through-spindle coolant pump (high-pressure) | `PUMP-TSC-01` | Coolant unit, rear of machine | Mechanics | High-pressure through-spindle coolant (TSC); up to 70 bar; feeds via spindle centre bore |
| Flood coolant pump | `PUMP-FLOOD-01` | Coolant unit, rear of machine | Mechanics | Low-pressure flood coolant for enclosure wash-down and nozzle manifold |
| Coolant nozzle manifold | `MANIFOLD-COOL-01` | Inside enclosure, spindle head | Mechanics | 6-nozzle adjustable manifold; directs coolant to cutting zone |
| Chip conveyor | `CONV-CHIP-01` | Base of machine, rear discharge | Mechanics | Hinge-belt type; discharges metal swarf into chip bin outside enclosure |
| Coolant tank (machine-integrated) | `TANK-INT-COOL-01` | Under machine bed | Mechanics | Feeds `PUMP-TSC-01` and `PUMP-FLOOD-01`; level sensor present; connects to zone supply at `VALVE-CNC-COOL-01` |

#### Automatic Tool Changer (ATC)

| Component | ID / Label | Location on Machine | Owning Dept | Specification / Notes |
| :--- | :--- | :--- | :--- | :--- |
| ATC magazine | `ATC-MAG-01` | Right side of column | Mechanics / Electrical | 40-station chain-type magazine; stores HSK-A63 tool holders |
| ATC arm & gripper | `ATC-ARM-01` | Column face | Mechanics / Electrical | Dual-arm swing-type; pneumatically actuated tool clamp/unclamp |
| Tool presence sensor | `SENS-TOOL-01` | ATC magazine stations | Electrical | Inductive sensors confirm tool seating; sends status to MAZATROL controller |

#### CNC Controller

| Component | ID / Label | Location on Machine | Owning Dept | Specification / Notes |
| :--- | :--- | :--- | :--- | :--- |
| MAZATROL SmoothX controller | `CNC-CTRL-01` | Operator panel, front of machine | Electrical | 19" touchscreen; MAZATROL / EIA/ISO G-code; Ethernet connectivity for DNC |
| Operator panel & E-stop | `PANEL-OP-01` | Front of machine, swivel arm | Electrical | Main operator interface; red E-stop mushroom button; mode selector |

#### Enclosure & Safety

| Component | ID / Label | Location on Machine | Owning Dept | Specification / Notes |
| :--- | :--- | :--- | :--- | :--- |
| Machine enclosure (full splash guard) | `ENCL-CNC-01` | Full machine wrap | Mechanics / EHS | Sheet steel; prevents coolant and chip egress during cutting |
| Main enclosure door (front) | `DOOR-CNC-F` | Front face | EHS / Mechanics | Sliding door; interlocked — spindle inhibited when open |
| Chip collection bin | `BIN-CHIP-01` | External, behind machine (rear) | Mechanics | Receives discharge from `CONV-CHIP-01`; manual emptying required |

---

## Zone 2 — Electronics Assembly (`Electronics_Assembly`)

**Machine / Line:** SMT assembly line — DEK Horizon 03i solder paste printer → Yamaha YSM20R pick-and-place → Heller 1809 MK5 reflow oven (in-line, west-to-east flow).
**Zone mapping:** this zone contains one line. `ENV_SENSOR_ZONE_ASSEMBLY` readings reflect the operating state of the SMT line directly.

### Zone Profile

| Attribute | Detail |
| :--- | :--- |
| **Zone Sensor** | `ENV_SENSOR_ZONE_ASSEMBLY` |
| **Hall Location** | East Side |
| **North boundary** | Exterior wall — ventilation duct `DUCT-NORTH-E` |
| **East boundary** | Emergency exit `EXIT-EAST` |
| **South boundary** | Main corridor & entry `ENTRY-SOUTH` |
| **West boundary** | Central partition `PART-01` |
| **Primary hazards** | Electrostatic discharge (ESD) at low humidity, solder flux fumes (rosin/colophony), reflow oven exhaust, PCB contamination |

### Zone Ambient Thresholds (`ENV_SENSOR_ZONE_ASSEMBLY`)

| Metric | Normal Range | Warning | Critical | Associated Risk |
| :--- | :--- | :--- | :--- | :--- |
| Ambient temperature | 20.5–21.5 °C | > 25 °C or < 18 °C | > 26 °C | Solder paste viscosity degradation; IPC-A-610 environment breach |
| Relative humidity | 50–55 % | < 30 % | < 20 % or > 70 % | < 30 % = ESD risk; > 70 % = board corrosion |
| Carbon monoxide (CO) | 1.5–3 ppm | > 10 ppm | > 25 ppm | Flux fume overload / fume extractor failure |
| Particulates (PM2.5) | 3–8 µg/m³ | > 35 µg/m³ | > 75 µg/m³ | Fume extractor failure or elevated soldering activity |
| Carbon dioxide (CO₂) | 500–900 ppm | > 1 000 ppm | > 1 500 ppm | AHU supply failure |

---

### Zone Hardware Register

#### HVAC & Air Handling

| Hardware Item | ID / Label | Location in Zone | Owning Dept | Notes |
| :--- | :--- | :--- | :--- | :--- |
| Air handling unit | `AHU-ASSEMBLY-01` | North wall / roof, ducted to `DUCT-NORTH-E` | Facilities | Temperature and humidity conditioning for the entire zone |
| Integrated steam humidifier | `HUM-ASSEMBLY-01` (Condair CP3) | Inside `AHU-ASSEMBLY-01` | Facilities / Electrical | Humidity setpoint 52 % RH; electrical supply via breaker **CB-14**, Electrical Room E2 |
| BMS control terminal | `BMS-T3` | Control Room 104 | Facilities / Electrical | Building management system interface for `AHU-ASSEMBLY-01`; setpoints 21.0 °C / 52 % RH |

#### Fume Extraction (Zone-Level)

| Hardware Item | ID / Label | Location in Zone | Owning Dept | Notes |
| :--- | :--- | :--- | :--- | :--- |
| Reflow oven exhaust duct connection | `DUCT-REFLOW-01` | North wall, above Heller 1809 MK5 | Facilities / Mechanics | Connects reflow oven exhaust to `DUCT-NORTH-E`; primary zone flux fume path |
| Paste printer fume extractor | `FUME-EXT-PRINTER` (Weller Zero-Smog TL) | Above DEK Horizon 03i | EHS / Mechanics | Duct-connected to `DUCT-NORTH-E`; HEPA + activated carbon filter |

#### ESD Control

| Hardware Item | ID / Label | Location in Zone | Owning Dept | Notes |
| :--- | :--- | :--- | :--- | :--- |
| ESD wrist-strap tester | `ESD-TEST-01` | Zone entrance, south side | EHS | IPC-A-610 Rev G §8.3 compliance verification point |
| ESD flooring / matting system | `ESD-FLOOR-ZONE2` | Full zone floor area | EHS / Facilities | Conductive; minimum 30 % RH required for effective conductivity |

#### Fire Suppression & Safety

| Hardware Item | ID / Label | Location in Zone | Owning Dept | Notes |
| :--- | :--- | :--- | :--- | :--- |
| High-pressure fine water mist system | `SUPPRESS-ASSY-01` | Zone ceiling, full coverage | EHS | Rated for electronics areas; fine mist — not a CO₂ flood or open-water system |
| Portable CO₂ extinguisher | `EXT-ASSY-E` | East exit `EXIT-EAST` | EHS | CO₂ unit |
| Portable CO₂ extinguisher | `EXT-ASSY-S` | South main entrance `ENTRY-SOUTH` | EHS | CO₂ unit |

---

### Machine Sub-Components — SMT Line

#### Station 1 — DEK Horizon 03i Solder Paste Printer

| Component | ID / Label | Location on Machine | Owning Dept | Specification / Notes |
| :--- | :--- | :--- | :--- | :--- |
| Squeegee head assembly | `SQGEE-DEK-01` | Print head carriage | Mechanics | Dual-blade metal squeegee; front and rear blades individually pressure-controlled |
| Print head carriage drive | `MTR-DEK-CARR-01` | Carriage rail, top of printer | Electrical | Servo-driven Y-axis traverse; belt and ballscrew |
| Stencil frame & clamp | `STENCIL-DEK-01` | Print table, centre | Mechanics | Snap-in stencil frame; pneumatic clamp; stencil thickness typically 0.12–0.15 mm |
| Board support system (tooling pins + rails) | `SUPPORT-DEK-01` | Print table, lower | Mechanics | Adjustable tooling pins and edge rails; prevents board flex during print stroke |
| Vision alignment system (2D + 3D) | `VISION-DEK-01` | Overhead camera gantry | Electrical | Dual camera — 2D fiducial alignment + 3D paste height inspection post-print |
| Paste reservoir & dispenser | `PASTE-DEK-01` | Print head, between blades | Mechanics | Solder paste cartridge or reservoir; Kester R&R or equivalent no-clean paste |
| Conveyor (entry / exit) | `CONV-DEK-IN` / `CONV-DEK-OUT` | Left and right of print table | Mechanics | Servo-driven edge-belt conveyor; adjustable width |

#### Station 2 — Yamaha YSM20R Pick-and-Place

| Component | ID / Label | Location on Machine | Owning Dept | Specification / Notes |
| :--- | :--- | :--- | :--- | :--- |
| Dual-gantry beam assembly | `GANTRY-YSM-01` / `GANTRY-YSM-02` | Upper machine frame, two parallel beams | Electrical / Mechanics | Independent dual gantry; each carries one placement head |
| Rotary placement head (×2) | `HEAD-YSM-01` / `HEAD-YSM-02` | Respective gantry beams | Mechanics / Electrical | 16-nozzle rotary head per beam; interchangeable nozzle sets |
| Nozzle sets | `NOZZLE-YSM-STD` / `NOZZLE-YSM-FINE` | Head storage rack | Mechanics | Standard (0402–QFP) and fine-pitch (01005, micro-BGA) sets; stored on head rack |
| Feeder rack (×2) | `FEEDER-YSM-F` / `FEEDER-YSM-R` | Front and rear feeder banks | Mechanics / Electrical | 66 feeder slots per bank (132 total); electric tape feeders; auto-loading capable |
| Board conveyor | `CONV-YSM-01` | Centre of machine, left-to-right flow | Mechanics | Dual-rail servo conveyor; SMEMA-compliant handoff with adjacent stations |
| Vision system — component camera | `VISION-YSM-COMP` | Under head, upward-looking | Electrical | High-speed CMOS camera; 2D component recognition and rotation correction |
| Vision system — board camera | `VISION-YSM-BOARD` | Head-mounted, downward-looking | Electrical | Fiducial recognition and bad-mark detection |
| Servo controller cabinet | `ELEC-CAB-YSM-01` | Right side panel of machine | Electrical | Houses all gantry servo drives and I/O; fan-cooled |

#### Station 3 — Heller 1809 MK5 Reflow Oven

| Component | ID / Label | Location on Machine | Owning Dept | Specification / Notes |
| :--- | :--- | :--- | :--- | :--- |
| Heating zones (9 top + 9 bottom) | `ZONE-REFLOW-01` to `ZONE-REFLOW-09` | Oven tunnel, top and bottom arrays | Electrical | Forced convection; each zone independently temperature-controlled; typical peak 245–260 °C for SAC305 |
| Zone heating elements | `ELEM-REFLOW-T01…T09` / `ELEM-REFLOW-B01…B09` | Top and bottom of each oven zone | Electrical | Nichrome elements; monitored by individual thermocouples |
| Zone thermocouples | `TC-REFLOW-01` to `TC-REFLOW-18` | Top and bottom of each zone | Electrical | Type K thermocouples; one per heating element bank; feedback to oven controller |
| Conveyor drive motor | `MTR-REFLOW-CONV` | Right side of oven base | Electrical / Mechanics | Chain-driven mesh belt; speed-controlled by oven PLC; board transit time = soldering profile duration |
| Conveyor mesh belt | `BELT-REFLOW-01` | Full tunnel length | Mechanics | Stainless steel mesh; width-adjustable edge rails for board width |
| Flux exhaust blower & duct | `BLOWER-REFLOW-01` | Top of oven, exhaust port | Mechanics / Facilities | Centrifugal blower; exhausts reflow fumes via `DUCT-REFLOW-01` to `DUCT-NORTH-E` |
| Flux management / condensate collector | `FLUX-COLL-01` | Under oven hood, condensate trays | Mechanics | Collects condensed flux rosin; requires periodic draining and cleaning |
| Cooling zone fan array | `FAN-COOL-REFLOW` | Exit end of oven tunnel | Electrical / Mechanics | Forced-air cooling; drops board from peak to below 100 °C before exit |
| Oven controller & profile display | `CTRL-REFLOW-01` | Operator panel, right side | Electrical | Colour touchscreen; stores named reflow profiles; logs zone temperatures continuously |
| Nitrogen supply connection (optional) | `N2-INLET-REFLOW` | Rear of oven | Facilities | Blanket nitrogen for low-oxygen reflow; valve closed when not in use |

---

## Emergency Contacts (Facility-Wide)

| Role | Contact |
| :--- | :--- |
| Mechanics on-call | ext. 2201 |
| Electrical on-call | ext. 2202 |
| Facilities on-call | ext. 2203 |
| EHS hotline (internal) | ext. 911 |
| EHS hotline (external) | 555-0199 |
| HVAC contractor (AirTech Services, 24 h) | 555-0142 |
