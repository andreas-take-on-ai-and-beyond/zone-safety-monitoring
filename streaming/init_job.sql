-- =============================================================================
-- Zone Safety Alert Job — windowed aggregation with suppression
--
-- DESIGN INTENT
-- -------------
-- Flink's role: decide WHETHER to forward to the agent, not WHAT it means.
-- All classification (department, urgency, root cause) is done by the wxO agent.
--
-- ALERT FATIGUE PROBLEM
-- ---------------------
-- A row-level WHERE filter fires on every 5-second reading above a threshold.
-- One 4-minute heating event → ~48 LLM calls all describing the same incident.
--
-- SOLUTION: TWO-LAYER SUPPRESSION
-- --------------------------------
-- Layer 1 (here, Flink): 60-second tumbling window aggregation.
--   • AVG the six signals over 60 s (12 readings) before evaluating thresholds.
--   • Single-spike noise (one bad reading in a 60-s window) is absorbed by the
--     average and does not trigger an alert.
--   • Sustained conditions (AVG still above threshold after 60 s) do trigger.
--   • Output rate: at most 1 alert per sensor per 60-second window.
--   • 12× reduction vs row-level filter before the agent is even involved.
--
-- Layer 2 (agent_bridge.py): per-sensor cooldown timer (default 300 s / 5 min).
--   • Even if Flink emits once per minute, the bridge suppresses re-invocation
--     until the cooldown expires.
--   • Configurable via ALERT_COOLDOWN_SECONDS env var.
--   • Combined effect: at most 1 LLM call per sensor per 5-minute incident window.
--
-- REAL-WORLD EQUIVALENT
-- ----------------------
-- This pattern is standard in industrial systems:
--   • Flink window  ≈  DCS/SCADA "alarm deadband" + "alarm delay" filter
--   • Bridge cooldown ≈  "re-alarm suppression timer" (IEC 62682 / ISA-18.2)
--   • Together they implement "alarm rationalisation" — only meaningful,
--     actionable state changes reach the operator / LLM.
--
-- ZONE-SPECIFIC THRESHOLDS (calibrated per operational environment)
-- ------------------------------------------------------------------
--   Temperature:
--     ENV_SENSOR_ZONE_CNC      : 38.0 °C  (heavy shop floor; >38°C = thermal emergency)
--     ENV_SENSOR_ZONE_ASSEMBLY : 26.0 °C  (electronics; >26°C = solder/IPC risk)
--     Default                  : 38.0 °C  (safe fallback for any new zone)
--   Life-safety signals (zone-independent):
--     CO   > 15.0 ppm  — early combustion / coolant fire / flux fume signal
--                         (OSHA PEL 50 ppm 8h TWA; 15 ppm gives operator lead time)
--     PM2.5 > 35.0 µg/m³ — sustained smoke / metalworking dust (WHO 24h limit)
--   ESD/quality signals (Assembly zone only):
--     humidity < 30.0 % — ESD-safe floor breached (IPC-A-610 requires ≥30 %;
--                          below this, sensitive IC assembly must be paused).
--                          Scenario: HVAC_HUMIDIFIER_FAILURE
-- =============================================================================

-- 1. Source table with event-time watermark for windowing
CREATE TABLE source_sensor_data (
    `timestamp`   STRING,
    sensor_id     STRING,
    zone          STRING,
    temperature_c DOUBLE,
    pressure_hpa  DOUBLE,
    humidity_pct  DOUBLE,
    co2_ppm       DOUBLE,
    co_ppm        DOUBLE,
    pm25_ugm3     DOUBLE,
    -- Derive a proper TIMESTAMP column from the string field for windowing
    event_time AS TO_TIMESTAMP(`timestamp`, 'yyyy-MM-dd HH:mm:ss'),
    WATERMARK FOR event_time AS event_time - INTERVAL '10' SECOND
) WITH (
    'connector'                     = 'kafka',
    'topic'                         = 'env_sensor_data',
    'properties.bootstrap.servers'  = 'kafka:29092',
    'scan.startup.mode'             = 'latest-offset',
    'format'                        = 'json'
);

-- 2. Sink: windowed alert aggregates for the agent
CREATE TABLE sink_sensor_alerts (
    `timestamp`      STRING,
    sensor_id        STRING,
    zone             STRING,
    alert_type       STRING,
    temperature_c    DOUBLE,
    pressure_hpa     DOUBLE,
    humidity_pct     DOUBLE,
    co2_ppm          DOUBLE,
    co_ppm           DOUBLE,
    pm25_ugm3        DOUBLE,
    current_value    DOUBLE,
    simulated_scenario STRING,
    message          STRING
) WITH (
    'connector'                    = 'kafka',
    'topic'                        = 'sensor_alerts',
    'properties.bootstrap.servers' = 'kafka:29092',
    'format'                       = 'json'
);

-- 3. Windowed aggregation — 60-second tumbling windows, alert on sustained conditions
--
--    AVG over 12 readings (5 s × 12 = 60 s) before evaluating thresholds.
--    A single spike in one reading does not trigger; a sustained condition does.
--    Output: at most one alert per sensor per 60-second window.

INSERT INTO sink_sensor_alerts
SELECT
    CAST(TUMBLE_END(event_time, INTERVAL '60' SECOND) AS STRING) AS `timestamp`,
    sensor_id,
    zone,
    'ENVIRONMENT_ALERT'  AS alert_type,
    AVG(temperature_c)   AS temperature_c,
    AVG(pressure_hpa)    AS pressure_hpa,
    AVG(humidity_pct)    AS humidity_pct,
    AVG(co2_ppm)         AS co2_ppm,
    AVG(co_ppm)          AS co_ppm,
    AVG(pm25_ugm3)       AS pm25_ugm3,
    AVG(temperature_c)   AS current_value,
    'ENVIRONMENT_ALERT'  AS simulated_scenario,
    CONCAT(
        'Sustained environment alert — zone ', zone,
        ' (', sensor_id, ')',
        ' [60s avg]',
        ': temp=',  CAST(CAST(AVG(temperature_c) AS DECIMAL(5,2)) AS STRING), '°C',
        ' hum=',    CAST(CAST(AVG(humidity_pct)  AS DECIMAL(5,1)) AS STRING), '%',
        ' CO=',     CAST(CAST(AVG(co_ppm)        AS DECIMAL(5,1)) AS STRING), 'ppm',
        ' PM2.5=',  CAST(CAST(AVG(pm25_ugm3)     AS DECIMAL(5,1)) AS STRING), 'ug/m3'
    ) AS message
FROM TABLE(
    TUMBLE(TABLE source_sensor_data, DESCRIPTOR(event_time), INTERVAL '60' SECOND)
)
GROUP BY
    TUMBLE(event_time, INTERVAL '60' SECOND),
    sensor_id,
    zone
HAVING
    -- Zone-specific temperature thresholds (calibrated per operational environment)
    (sensor_id = 'ENV_SENSOR_ZONE_CNC'      AND AVG(temperature_c) > 38.0)
    OR (sensor_id = 'ENV_SENSOR_ZONE_ASSEMBLY' AND AVG(temperature_c) > 26.0)
    OR (sensor_id NOT IN ('ENV_SENSOR_ZONE_CNC', 'ENV_SENSOR_ZONE_ASSEMBLY') AND AVG(temperature_c) > 38.0)
    -- Life-safety signals — trigger regardless of zone or temperature
    -- CO > 15 ppm: early combustion / coolant fire / flux fume signal
    -- PM2.5 > 35 µg/m³: WHO 24h air quality limit (sustained smoke or metalworking dust)
    OR AVG(co_ppm)    > 15.0
    OR AVG(pm25_ugm3) > 35.0
    -- ESD quality signal — Assembly zone only
    -- Humidity < 30 %: IPC-A-610 ESD-safe floor; HVAC humidifier failure scenario
    OR (sensor_id = 'ENV_SENSOR_ZONE_ASSEMBLY' AND AVG(humidity_pct) < 30.0);
