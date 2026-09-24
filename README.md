# Zone Safety Command Center

An event-driven AI agent pipeline for industrial zone safety monitoring — fully local infrastructure, cloud-grade LLM.

Synthetic sensor data streams from two simulated manufacturing zone sensors through **Apache Kafka**, is classified by **Apache Flink** using multi-signal threshold logic, and dispatches a **native watsonx Orchestrate agent** (`zone_safety_native`) that interprets readings, checks cross-session incident history, retrieves zone equipment facts, and emits structured maintenance dispatches to a live **Carbon React dashboard**.

**LLM:** `gpt-oss-120b` via Groq, routed through the watsonx Orchestrate AI Gateway.  
**Infrastructure:** Kafka + Flink run in Docker on your Mac. watsonx Orchestrate Developer Edition runs locally.

---

## Architecture

```
producers/sensor_cnc.py / sensor_assembly.py   (Python — synthetic sensor data)
        │  Kafka topic: env_sensor_data  (every 5 s)
        ▼
Apache Flink  —  streaming/init_job.sql
        │  60-second tumbling window, multi-signal threshold logic
        │  Kafka topic: sensor_alerts  (threshold-crossing events only)
        ▼
bridge/agent_bridge.py   (Python — confluent-kafka consumer)
        │  180 s per-sensor cooldown
        │  Writes sensor_log.json      (every tick — telemetry charts)
        │  Writes alert_history.json   (every dispatch — persistent, never trimmed)
        ▼
bridge/wxo_client.py  →  watsonx Orchestrate DE (:4321)
                        │  zone_safety_native (agents/wxo_native_agent.yaml)
                        │  LLM: gpt-oss-120b via Groq (AI Gateway)
                        ▼
                dashboard_log.json
                        │
                server.cjs  (Express :4173)
                        │
            http://localhost:4173
```

**Ports:**

| Service | Port | URL |
|---|---|---|
| Kafka broker | 9092 | `localhost:9092` |
| Kafka UI | 8090 | http://localhost:8090 |
| Flink Web UI | 8081 | http://localhost:8081 |
| watsonx Orchestrate DE | 4321 | http://localhost:4321 |
| Dashboard | 4173 | http://localhost:4173 |

---

## Prerequisites & Installation

Before starting the demo on your local machine, ensure the following tools are installed:

| Component | Required Version | Purpose / Installation |
|---|---|---|
| **Python** | ≥ 3.11 | Runs synthetic sensor producers (`producers/sensor_*.py`) and event bridge (`bridge/agent_bridge.py`). |
| **Node.js & npm** | Node ≥ 18, npm ≥ 9 | Compiles Carbon React v11 frontend and runs Express server (`server.cjs`). |
| **Docker / Podman** | latest | Runs Apache Kafka (KRaft), Kafka UI, Apache Flink JobManager & TaskManager via `streaming/docker-compose.yml`. |
| **watsonx Orchestrate ADK** | ≥ 2.17.0 | CLI for Developer Edition server lifecycle, agent YAML compilation, and tool imports (`pip install ibm-watsonx-orchestrate`). |
| **IBM Entitlement Key** | Valid Container Registry Key | Required to pull Developer Edition container images from `cp.icr.io` via `myibm`. |
| **watsonx Orchestrate SaaS Tenant** | Active Instance | Required for SaaS cloud routing / AI Gateway proxy (`WO_INSTANCE` + `WO_API_KEY`). |

---

### Important: watsonx Orchestrate SaaS Tenant Dependency (Cloud Model)

This demo uses the high-performance reasoning model `groq/openai/gpt-oss-120b` (specified in [`wxo_native_agent.yaml`](wxo_native_agent.yaml:12)) routed through the **watsonx Orchestrate AI Gateway**.

To make use of this model, your local Developer Edition connects to a live **watsonx Orchestrate SaaS tenant**:
- **SaaS Instance URL (`WO_INSTANCE`)**: Your tenant instance URL (e.g. `https://api.eu-central-1.dl.watson-orchestrate.ibm.com/instances/...` or `https://api.us-south.watson-orchestrate.cloud.ibm.com/instances/...`).
- **SaaS API Key (`WO_API_KEY`)**: An IBM Cloud API key associated with your watsonx Orchestrate SaaS instance.
- **Entitlement Key (`WO_ENTITLEMENT_KEY`)**: Your IBM Container Registry entitlement key from [myibm.ibm.com](https://myibm.ibm.com/products-services/containerlibrary).

> **Alternative: Local LLM with Ollama (Zero Cloud Dependency):**
> If you do not have SaaS tenant access, you can run an offline local model (e.g. `llama3.3:70b` or `granite3-dense:8b`) via [Ollama](https://ollama.com):
> 1. Install and start Ollama locally (`ollama run llama3.3`).
> 2. Register the local model in watsonx Orchestrate Developer Edition or update `llm:` in [`wxo_native_agent.yaml`](wxo_native_agent.yaml:12) to target your local model provider.
> 3. Note: The agent instructions utilize deep multi-step ReAct tool-calling; a capable model with strong JSON formatting and tool compliance (e.g. `llama3.3` or `gpt-oss-120b`) is required.

---

### Docker Context Note (macOS / Lima VM)

When using watsonx Orchestrate Developer Edition on macOS, Docker runs inside the `ibm-watsonx-orchestrate` Lima virtual machine.

Before launching Kafka and Flink with `docker-compose`, switch your Docker context:
```bash
docker context use ibm-watsonx-orchestrate
docker info   # Verify: Server version must appear without socket errors
```
*(Note: With the Lima VM Docker context, use `docker-compose` or `docker compose -f streaming/docker-compose.yml`).*
*(If you are running standard Docker Desktop on Linux/macOS/Windows without the Lima VM, ensure your default Docker context is active).*

---

## Setup (One-Time)

### 1 — Install Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2 — Configure watsonx Orchestrate Developer Edition `.env`

Create an environment file at a path of your choice (e.g. `~/.wxo-dev-edition/.env`) and populate it with your credentials.
A ready-to-fill template is provided at [`.env.wxo-dev-edition.example`](.env.wxo-dev-edition.example) in this repository.

> **Security:** Generate a unique, strong password for every credential field.
> Use `openssl rand -base64 32` for each password and for `DB_ENCRYPTION_KEY`.
> **Never reuse default or well-known values for any of these fields.**
> The `.env` file must never be committed — it is already covered by `.gitignore`.

```env
# ── Developer Edition Image Source ──
WO_DEVELOPER_EDITION_SOURCE=myibm
WO_ENTITLEMENT_KEY=<your_cp_icr_io_entitlement_key>

# ── Cloud LLM & Service Proxy (watsonx Orchestrate SaaS Tenant) ──
# EU:       https://api.eu-central-1.dl.watson-orchestrate.ibm.com/instances/<instance-id>
# US South: https://api.us-south.watson-orchestrate.cloud.ibm.com/instances/<instance-id>
WO_INSTANCE=<your-region-endpoint>/instances/<your-instance-id>
WO_API_KEY=<your_watsonx_orchestrate_api_key>
AUTHORIZATION_URL=https://account-iam.platform.saas.ibm.com/api/2.0/apikeys/token

# ── Internal Service Credentials (minimum 18 characters for all passwords) ──
# Generate each password with: openssl rand -base64 32
MINIO_ROOT_USER=<choose-a-username>
LANGFUSE_USERNAME=<choose-a-username>
MCP_GATEWAY_BASIC_USER=<choose-a-username>
CLICKHOUSE_USER=<choose-a-username>

POSTGRES_PASSWORD=<generate: openssl rand -base64 32>
MINIO_ROOT_PASSWORD=<generate: openssl rand -base64 32>
LANGFUSE_PASSWORD=<generate: openssl rand -base64 32>
MCP_GATEWAY_BASIC_PASSWORD=<generate: openssl rand -base64 32>
MCP_GATEWAY_ADMIN_PASSWORD=<generate: openssl rand -base64 32>
CLICKHOUSE_PASSWORD=<generate: openssl rand -base64 32>
ES_PASSWORD=<generate: openssl rand -base64 32>
MILVUS_PASSWORD=<generate: openssl rand -base64 32>
DB_ENCRYPTION_KEY=<generate: openssl rand -base64 32>
```

### 3 — Install Node.js frontend dependencies

```bash
cd frontend
npm install
cd ..
```

---

## Running the demo

Open **five terminals** from the project root:

### Terminal 1 — watsonx Orchestrate Developer Edition

Start the wxO server, activate the local environment, and import the agent and tools:

```bash
# 1. Start the wxO Developer Edition server (point to your .env path)
orchestrate server start -e "/path/to/wxo-dev-edition/.env" --accept-terms-and-conditions

# 2. Activate the local environment
orchestrate env activate local

# 3. Import the native agent and the 5 custom tools
./scripts/import-all.sh

# 4. Verify agent and tools
orchestrate agents list
orchestrate tools list

# 5. Get and copy the UUID next to zone_safety_native (needed for Terminal 4)
orchestrate agents list -v
```

### Terminal 2 — Infrastructure (Kafka + Flink)

```bash
# 1. Switch to the active wxO Docker context
docker context use ibm-watsonx-orchestrate

# 2. Start Kafka (KRaft), Kafka UI, Flink JobManager, and TaskManager
cd streaming && docker-compose up -d && cd ..

# 3. Wait ~15–20 s, then submit the Flink SQL job:
docker exec -it flink-jobmanager ./bin/sql-client.sh -f /opt/flink/usrlib/init_job.sql
```

**Verify:**
- Flink UI at http://localhost:8081 → Jobs → Running Jobs (one job running: `sink_sensor_alerts`)
- Kafka UI at http://localhost:8090

### Terminal 3 — Dashboard

Build the frontend bundle and start the Express server:

```bash
./scripts/start-dashboard.sh
```

Access the UI at http://localhost:4173.

### Terminal 4 — Agent bridge

Activate the virtual environment and start the bridge with the agent UUID from Terminal 1:

```bash
source .venv/bin/activate
WXO_AGENT_ID=<YOUR-AGENT-ID> ./scripts/run_wxo_bridge.sh
```

The bridge reads the bearer token automatically from `~/.cache/orchestrate/credentials.yaml`.

### Terminal 5 — Scenario runner

Activate the virtual environment and launch the interactive scenario runner:

```bash
source .venv/bin/activate
./scripts/scenario_runner.sh
```

Pick **option `0`** to start both zones in `NORMAL` mode. Then switch to any alert scenario from the menu without restarting anything else.

---

## Demo scenarios

### Zone A — CNC Machining (`producers/sensor_cnc.py`)

| # | Scenario | Alert | Signal pattern |
|---|---|---|---|
| 1 | `NORMAL` | ✅ None | Healthy shift baseline |
| 2 | `TOOL_BINDING_FIRE` | 🔴 CRITICAL / EHS | PM2.5 ↑65 µg/m³ · CO ↑25 ppm · Temp ↑42 °C — tri-spike |
| 3 | `CHIP_BLOWOFF` | 🟡 Benign | PM2.5 spikes 1 tick then drops — no dispatch |
| 4 | `COOLANT_LEAK` | 🔴 CRITICAL / Mechanics | Humidity ↑75 % · Temp ↑40 °C · CO flat |
| 5 | `BEARING_OVERHEAT` | 🔴 CRITICAL / Electrical | Temp ↑41 °C · Humidity ↓28 % · CO slight rise |

### Zone B — Electronics Assembly (`producers/sensor_assembly.py`)

| # | Scenario | Alert | Signal pattern |
|---|---|---|---|
| 6 | `NORMAL` | ✅ None | Stable HVAC, CO₂ tracks occupancy |
| 7 | `FUME_EXTRACTOR_FAILURE` | 🟠 WARNING / EHS | PM2.5 ↑40 µg/m³ · CO ↑15 ppm · Temp flat |
| 8 | `HVAC_HUMIDIFIER_FAILURE` | 🟡 WARNING / Facilities | Humidity 52 % → 28 % — ESD risk |
| 9 | `HVAC_BREAKDOWN` | 🟡 WARNING / Facilities | CO₂ ↑1 600+ ppm · Temp ↑27 °C · CO/PM2.5 flat |

---

## Agent tools

Five tools give the agent context that a static rule system cannot have:

| Tool | Purpose |
|---|---|
| `check_zone_ambient_conditions` | Five-signal assessment calibrated to zone baselines; deviation from baseline and failure-mode vocabulary |
| `get_alert_history` | Cross-session dispatch history + incident trajectory (ESCALATING / SUSTAINED CRITICAL / RECOVERING) from `alert_history.json` |
| `get_prior_dispatches` | Full text of prior dispatch messages — prevents repeating recommendations that did not resolve the condition |
| `get_zone_equipment_info` | Zone equipment register: machine IDs, fire suppression, extinguisher locations, coolant valve, humidifier breaker, emergency extensions |
| `prepare_dispatch_payload` | Serialises the dispatch as `DISPATCH_PAYLOAD::{...}` for reliable extraction by the bridge |

---

## Configuration reference

| Variable | Default | Description |
|---|---|---|
| `ALERT_COOLDOWN_SECONDS` | `180` | Per-sensor cooldown between LLM dispatches (seconds) |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker address — used by both sensor producers and the agent bridge. Override to point at a remote or managed broker without editing source. |
| `WXO_BASE_URL` | `http://localhost:4321/api/v1` | watsonx Orchestrate DE API base URL |
| `WXO_AGENT_ID` | _(required)_ | UUID from `orchestrate agents list -v` |
| `WXO_BEARER_TOKEN` | _(auto-read from `~/.cache/orchestrate/credentials.yaml`)_ | wxO bearer token — read fresh on every agent call so token rotation during a long-running session is handled transparently |
| `WXO_TIMEOUT_SECONDS` | `120` | HTTP timeout for wxO API calls |
| `WXO_DEBUG_DUMP` | `0` | Set to `1` to log safe agent response metadata (run ID, model, usage, step count) before each dispatch |
| `SCENARIO` | `NORMAL` | Sensor scenario — set via `scenario_runner.sh` or directly |
| `PORT` | `4173` | Dashboard port |

---

## Project structure

```
.
├── agents/                  # watsonx Orchestrate Native Agent & Tool Definitions
│   ├── wxo_native_agent.yaml # Native agent YAML (gpt-oss-120b / Granite)
│   └── wxo_native_tools.py   # 5 deterministic ReAct diagnostic tools
├── streaming/               # Stream Processing & Messaging Tier
│   ├── docker-compose.yml   # Kafka (KRaft) + Kafka UI + Flink cluster
│   ├── init_job.sql         # Flink SQL: Tumbling window & threshold query
│   └── lib/                 # Flink SQL Kafka connector JAR
├── producers/               # Synthetic Industrial IoT Sensor Streams
│   ├── sensor_cnc.py        # CNC Machining zone simulator (5s tick)
│   └── sensor_assembly.py   # Electronics Assembly zone simulator (5s tick)
├── bridge/                  # Event Bridge & Rate Limiter
│   ├── agent_bridge.py      # Kafka consumer, ISA-18.2 Cooldown & audit logger
│   └── wxo_client.py        # watsonx Orchestrate REST client
├── scripts/                 # Demo Automation & Lifecycle Scripts
│   ├── import-all.sh        # Imports tools & agent into wxO DE
│   ├── delete-all.sh        # Deletes tools & agent from wxO DE
│   ├── run_wxo_bridge.sh    # Launches agent bridge with bearer token
│   ├── scenario_runner.sh   # Interactive demo menu (10 scenarios)
│   └── start-dashboard.sh   # Builds React bundle & starts Express server
├── frontend/                # Carbon Design System v11 React Application
│   ├── src/                 # React 18 SPA (Dashboard, Telemetry, FloorPlan, Architecture)
│   ├── public/              # Standalone interactive presentations
│   └── vite.config.js
├── presentation/            # Standalone Presentation Artifacts
│   └── architecture-presentation.html
├── knowledge/               # Grounding Knowledge & Zone Equipment Register
│   └── zone_equipment_register.md
├── server.cjs               # Production Express static & log API server
└── requirements.txt         # Python dependencies
```

---

## Troubleshooting

**`docker-compose` not found / `unknown shorthand flag: 'd'`**
```bash
cd streaming && docker-compose up -d && cd ..
```

**Docker context points to wxO Lima socket**
```bash
docker context use default
docker info   # Server version should appear
```

**Flink job not running**
```bash
docker exec -it flink-jobmanager ./bin/sql-client.sh -f /opt/flink/usrlib/init_job.sql
```

**Dashboard shows no data**
`bridge/agent_bridge.py` writes both log files. Ensure Kafka, Flink, and the bridge are all running.

**Telemetry charts are flat**
The telemetry thread subscribes at `auto.offset.reset=latest`. Start the bridge before (or shortly after) launching the sensor scripts.

**`WXO_AGENT_ID is not set`**
```bash
orchestrate agents list -v      # copy UUID next to zone_safety_native
WXO_AGENT_ID=<uuid> ./scripts/run_wxo_bridge.sh
```

---

## Safe shut down

To stop all running infrastructure containers and the local watsonx Orchestrate Developer Edition server in one command:

```bash
docker context use ibm-watsonx-orchestrate && cd streaming && docker-compose down && cd .. && orchestrate server stop
```

### Detailed Tear Down

```bash
# 1. Stop Kafka + Flink containers
docker context use ibm-watsonx-orchestrate
cd streaming
docker-compose down

# Optional: also remove Kafka topic volume data for a clean reset
docker-compose down -v && rm -rf ../kafka-data/
cd ..

# 2. Stop watsonx Orchestrate Developer Edition server & Lima VM
orchestrate server stop
```

---

## Technology stack

| Layer | Technology |
|---|---|
| Synthetic sensors | Python — `producers/sensor_cnc.py`, `producers/sensor_assembly.py` |
| Message broker | Apache Kafka 7.6 (KRaft — no ZooKeeper) via Docker |
| Stream processing | Apache Flink 1.18.1 (Flink SQL, continuous query) via Docker (`streaming/`) |
| Agent bridge | Python + `confluent-kafka` (`bridge/`) |
| AI agent | watsonx Orchestrate Developer Edition — native agent (`agents/`), `react_intrinsic` style |
| LLM | `gpt-oss-120b` via Groq (routed through wxO AI Gateway) |
| Frontend | Carbon Design System v11 React (React 18 + Vite 5) (`frontend/`) |
| Dashboard server | Express (Node.js) (`server.cjs`) |
