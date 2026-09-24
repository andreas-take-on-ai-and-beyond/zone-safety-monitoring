/**
 * FloorPlan.jsx
 *
 * Factory floor plan tab — visualises the CNC Machining and Electronics Assembly
 * zones with their ENV_SENSOR suite nodes.  Each sensor node shows:
 *
 *   🟢 green  — INFO (all clear)
 *   🟡 yellow — WARNING (at least one reading above warn threshold)
 *   🔴 red    — CRITICAL (AI agent dispatched a CRITICAL alert)
 *
 * Status is derived from:
 *   • dashboard_log.json  — AI-dispatched urgency levels (polled every 3 s)
 *   • sensor_log.json     — raw metric readings for tooltip detail
 *
 * Clicking a sensor node opens a detail popover with the latest dispatch
 * message and key metric values.
 */

import React, {
  useState,
  useEffect,
  useCallback,
  useRef,
  useMemo,
} from 'react';
import BoldText from '../components/BoldText';
import { Grid, Column, Tag, InlineNotification } from '@carbon/react';
import {
  WarningAltFilled,
  CheckmarkFilled,
  WarningFilled,
} from '@carbon/icons-react';

// ── Poll interval ──────────────────────────────────────────────────────────────
const POLL_MS = 3000;

// ── Sensor / zone layout config ────────────────────────────────────────────────
// Positions are expressed in the SVG viewBox coordinate system (0 0 800 480).
const ZONES = [
  {
    id: 'CNC_Machining',
    label: 'CNC Machining',
    x: 60,
    y: 80,
    w: 300,
    h: 260,
    fillColour: '#161616',
    strokeColour: '#a56eff',
    iconX: 80,
    iconY: 105,
    // small machine illustration anchor
    machineX: 120,
    machineY: 230,
  },
  {
    id: 'Electronics_Assembly',
    label: 'Electronics Assembly',
    x: 430,
    y: 80,
    w: 310,
    h: 260,
    fillColour: '#161616',
    strokeColour: '#4589ff',
    iconX: 450,
    iconY: 105,
    machineX: 560,
    machineY: 230,
  },
];

const SENSOR_NODES = [
  {
    sensor_id: 'ENV_SENSOR_ZONE_CNC',
    zone: 'CNC_Machining',
    label: 'ENV_SENSOR\nCNC',
    x: 210,
    y: 200,
  },
  {
    sensor_id: 'ENV_SENSOR_ZONE_ASSEMBLY',
    zone: 'Electronics_Assembly',
    label: 'ENV_SENSOR\nAssembly',
    x: 585,
    y: 200,
  },
];

// ── Zone-specific sensor metric thresholds ────────────────────────────────────
// Calibrated per operational environment — prevents false-alarm "alert fatigue"
// in normal mode while correctly triggering on real incident sensor trails.
//
// CNC Machining: warm, dusty shop floor — higher baselines are normal
//   Temp warn 28.5 °C (spindle heat ok up to here), crit 38 °C
//   PM2.5 warn 25 µg/m³ (coolant mist ok), crit 35 µg/m³ (WHO 24h limit)
//   CO warn 8 ppm (tramp oil trace ok), crit 15 ppm (early combustion signal)
//   CO₂ warn 1 000 ppm / crit 1 500 ppm — standard indoor air quality
//   Humidity: not a primary alarm in CNC; humidity < 35 % triggers dry-run risk
//
// Electronics Assembly: tightly climate-controlled, ESD-sensitive
//   Temp warn 23 °C / crit 26 °C (IPC-A-610 solder paste stability)
//   PM2.5 warn 10 µg/m³ / crit 25 µg/m³ (semi-clean environment)
//   CO warn 8 ppm / crit 15 ppm (flux fume signal)
//   CO₂ warn 1 000 ppm / crit 1 500 ppm — ASHRAE 62.1 occupancy
//   Humidity low warn 30 % / low crit < 30 % (ANSI/ESD S20.20 static risk)
//   Humidity high warn 60 % / high crit 70 % (condensation / solder oxidation)
//
const THRESHOLDS = {
  ENV_SENSOR_ZONE_CNC: {
    temperature_c: { warn: 28.5, crit: 38.0 },
    pm25_ugm3:     { warn: 25.0, crit: 35.0 },
    co_ppm:        { warn:  8.0, crit: 15.0 },
    co2_ppm:       { warn: 1000, crit: 1500 },
    // humidity: low threshold only (dry-run / fire condition)
    humidity_low:  { warn: 35.0, crit: 28.0 },
  },
  ENV_SENSOR_ZONE_ASSEMBLY: {
    temperature_c: { warn: 23.0, crit: 26.0 },
    pm25_ugm3:     { warn: 10.0, crit: 25.0 },
    co_ppm:        { warn:  8.0, crit: 15.0 },
    co2_ppm:       { warn: 1000, crit: 1500 },
    // humidity: both low (ESD) and high (condensation) matter here
    humidity_low:  { warn: 30.0, crit: 25.0 },
    humidity_high: { warn: 60.0, crit: 70.0 },
  },
};

/** Return the threshold set for a given sensor id, falling back to CNC defaults. */
function getThresholds(sensorId) {
  return THRESHOLDS[sensorId] ?? THRESHOLDS['ENV_SENSOR_ZONE_CNC'];
}

// ── Status helpers ────────────────────────────────────────────────────────────
/**
 * Derive a status from the latest dashboard_log entry for this sensor.
 * CRITICAL > WARNING (derived from raw sensor reading) > OK
 *
 * Uses zone-specific thresholds so a CNC reading of 28 °C stays green while
 * an Assembly reading of 24 °C correctly turns yellow.
 */
function deriveSensorStatus(sensorId, dispatchMap, sensorMap) {
  const latestDispatch = dispatchMap[sensorId];
  if (latestDispatch?.urgency === 'CRITICAL') return 'critical';

  // Check raw metrics against zone-specific thresholds
  const reading = sensorMap[sensorId];
  if (reading) {
    const t = getThresholds(sensorId);

    // Standard high-value thresholds (temp, pm25, co, co2)
    const highChecks = ['temperature_c', 'pm25_ugm3', 'co_ppm', 'co2_ppm'];
    for (const metric of highChecks) {
      if (!t[metric]) continue;
      const v = reading[metric];
      if (v == null) continue;
      if (v >= t[metric].crit) return 'critical';
      if (v >= t[metric].warn) return 'warning';
    }

    // Humidity — low direction (ESD / dry-run risk)
    if (t.humidity_low) {
      const h = reading.humidity_pct;
      if (h != null) {
        if (h <= t.humidity_low.crit) return 'critical';
        if (h <= t.humidity_low.warn) return 'warning';
      }
    }

    // Humidity — high direction (condensation / solder oxidation, Assembly only)
    if (t.humidity_high) {
      const h = reading.humidity_pct;
      if (h != null) {
        if (h >= t.humidity_high.crit) return 'critical';
        if (h >= t.humidity_high.warn) return 'warning';
      }
    }

    // We have a reading and nothing breached a threshold → green
    return 'ok';
  }

  // INFO dispatch with no raw reading → green
  if (latestDispatch?.urgency === 'INFO') return 'ok';

  // Genuinely no data yet
  return 'unknown';
}

const STATUS_COLOURS = {
  critical: '#fa4d56',
  warning:  '#f1c21b',
  ok:       '#42be65',
  unknown:  '#6f6f6f',
};

const STATUS_GLOW = {
  critical: 'rgba(250,77,86,0.35)',
  warning:  'rgba(241,194,27,0.35)',
  ok:       'rgba(66,190,101,0.25)',
  unknown:  'rgba(111,111,111,0.2)',
};

function StatusIcon({ status, size = 20 }) {
  if (status === 'critical') return <WarningAltFilled size={size} style={{ fill: STATUS_COLOURS.critical }} aria-label="Critical" />;
  if (status === 'warning')  return <WarningFilled    size={size} style={{ fill: STATUS_COLOURS.warning }}  aria-label="Warning" />;
  if (status === 'ok')       return <CheckmarkFilled  size={size} style={{ fill: STATUS_COLOURS.ok }}       aria-label="OK" />;
  return null;
}

// ── Sensor Node SVG element ────────────────────────────────────────────────────
function SensorNode({ node, status, isSelected, onClick }) {
  const colour = STATUS_COLOURS[status];
  const glow   = STATUS_GLOW[status];
  const pulse  = status === 'critical' || status === 'warning';

  return (
    <g
      className={`floor-sensor-node floor-sensor-node--${status}${isSelected ? ' floor-sensor-node--selected' : ''}`}
      onClick={() => onClick(node.sensor_id)}
      style={{ cursor: 'pointer' }}
      role="button"
      aria-label={`${node.sensor_id} — ${status}`}
    >
      {/* Outer glow ring (animated for critical/warning) */}
      <circle
        cx={node.x}
        cy={node.y}
        r={28}
        fill="none"
        stroke={colour}
        strokeWidth={pulse ? 1.5 : 1}
        opacity={0.3}
        className={pulse ? 'sensor-pulse-ring' : ''}
      />

      {/* Background circle */}
      <circle
        cx={node.x}
        cy={node.y}
        r={20}
        fill={glow}
        stroke={colour}
        strokeWidth={isSelected ? 2.5 : 1.8}
      />

      {/* Status dot */}
      <circle cx={node.x} cy={node.y} r={7} fill={colour} />

      {/* Label */}
      {node.label.split('\n').map((line, i) => (
        <text
          key={i}
          x={node.x}
          y={node.y + 36 + i * 13}
          textAnchor="middle"
          fill="var(--cds-text-secondary)"
          fontSize="10"
          fontFamily="'IBM Plex Mono', monospace"
        >
          {line}
        </text>
      ))}
    </g>
  );
}

// ── Zone rectangle SVG element ─────────────────────────────────────────────────
function ZoneRect({ zone, zoneStatus }) {
  const colour = zone.strokeColour;
  return (
    <g>
      <rect
        x={zone.x}
        y={zone.y}
        width={zone.w}
        height={zone.h}
        rx={6}
        fill={zone.fillColour}
        stroke={colour}
        strokeWidth={2}
        opacity={0.95}
      />
      {/* Zone label bar at top */}
      <rect x={zone.x} y={zone.y} width={zone.w} height={28} rx={6} fill={colour} opacity={0.15} />
      <text
        x={zone.x + zone.w / 2}
        y={zone.y + 18}
        textAnchor="middle"
        fill={colour}
        fontSize="12"
        fontWeight="600"
        fontFamily="'IBM Plex Sans', 'Segoe UI', sans-serif"
        letterSpacing="0.04em"
      >
        {zone.label.toUpperCase()}
      </text>

      {/* Simple machine silhouette — CNC */}
      {zone.id === 'CNC_Machining' && (
        <g opacity={0.25} fill={colour}>
          {/* Base platform */}
          <rect x={zone.machineX - 55} y={zone.machineY + 25} width={110} height={12} rx={2} />
          {/* Machine body */}
          <rect x={zone.machineX - 35} y={zone.machineY - 10} width={70} height={36} rx={3} />
          {/* Spindle arm */}
          <rect x={zone.machineX - 6} y={zone.machineY - 40} width={12} height={32} rx={2} />
          {/* Spindle head */}
          <circle cx={zone.machineX} cy={zone.machineY - 46} r={8} />
          {/* Table */}
          <rect x={zone.machineX - 45} y={zone.machineY + 14} width={90} height={11} rx={2} />
        </g>
      )}

      {/* Simple PCB / workbench silhouette — Assembly */}
      {zone.id === 'Electronics_Assembly' && (
        <g opacity={0.25} fill={colour}>
          {/* Workbench */}
          <rect x={zone.machineX - 60} y={zone.machineY + 20} width={120} height={10} rx={2} />
          {/* Bench legs */}
          <rect x={zone.machineX - 52} y={zone.machineY + 30} width={8}  height={20} rx={1} />
          <rect x={zone.machineX + 44} y={zone.machineY + 30} width={8}  height={20} rx={1} />
          {/* PCB on bench */}
          <rect x={zone.machineX - 38} y={zone.machineY - 5}  width={76} height={26} rx={3} />
          {/* IC chips on PCB */}
          <rect x={zone.machineX - 28} y={zone.machineY + 2}  width={18} height={12} rx={1} />
          <rect x={zone.machineX + 10} y={zone.machineY + 2}  width={18} height={12} rx={1} />
          {/* Solder iron */}
          <rect x={zone.machineX + 36} y={zone.machineY - 30} width={5}  height={36} rx={2} />
          <polygon points={`${zone.machineX+38},${zone.machineY - 30} ${zone.machineX+34},${zone.machineY-44} ${zone.machineX+42},${zone.machineY-44}`} />
        </g>
      )}
    </g>
  );
}

// ── Detail popover ─────────────────────────────────────────────────────────────
const DETAIL_METRICS = [
  { key: 'temperature_c', label: 'Temperature', unit: '°C' },
  { key: 'co_ppm',        label: 'CO',          unit: ' ppm' },
  { key: 'pm25_ugm3',     label: 'PM2.5',       unit: ' µg/m³' },
  { key: 'co2_ppm',       label: 'CO₂',         unit: ' ppm' },
  { key: 'humidity_pct',  label: 'Humidity',     unit: '%' },
];

function SensorDetail({ sensorId, status, dispatchEntry, sensorReading }) {
  // Per-sensor threshold set — used to colour individual metric rows
  const t = getThresholds(sensorId);

  return (
    <div className="floor-detail-panel" aria-label={`Sensor detail: ${sensorId}`}>
      <div className="floor-detail-panel__header">
        <StatusIcon status={status} size={18} />
        <span className="floor-detail-panel__title">{sensorId.replace('ENV_SENSOR_ZONE_', '')}</span>
        <Tag
          type={status === 'critical' ? 'red' : status === 'warning' ? 'yellow' : status === 'ok' ? 'green' : 'gray'}
          size="sm"
        >
          {status === 'ok' ? 'ALL CLEAR' : status.toUpperCase()}
        </Tag>
      </div>

      {/* Latest sensor readings */}
      {sensorReading ? (
        <div className="floor-detail-panel__metrics">
          {DETAIL_METRICS.map(({ key, label, unit }) => {
            const val = sensorReading[key];
            // Derive per-metric colour using zone-specific thresholds
            let metricStatus = 'ok';
            if (val != null) {
              const thresh = t[key];   // standard high-value threshold (temp, pm25, co, co2)
              if (thresh) {
                if (val >= thresh.crit) metricStatus = 'critical';
                else if (val >= thresh.warn) metricStatus = 'warning';
              }
              // Humidity — low direction
              if (key === 'humidity_pct' && t.humidity_low) {
                if (val <= t.humidity_low.crit) metricStatus = 'critical';
                else if (val <= t.humidity_low.warn) metricStatus = 'warning';
              }
              // Humidity — high direction (Assembly only)
              if (key === 'humidity_pct' && t.humidity_high) {
                if (val >= t.humidity_high.crit) metricStatus = 'critical';
                else if (val >= t.humidity_high.warn && metricStatus !== 'critical') metricStatus = 'warning';
              }
            }
            return (
              <div key={key} className={`floor-metric floor-metric--${metricStatus}`}>
                <span className="floor-metric__label">{label}</span>
                <span className="floor-metric__value">
                  {val != null ? `${Number(val).toFixed(2)}${unit}` : '—'}
                </span>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="floor-detail-panel__no-data">No sensor reading available yet</p>
      )}

      {/* Latest AI dispatch */}
      {dispatchEntry && (
        <div className="floor-detail-panel__dispatch">
          <p className="floor-detail-panel__dispatch-label">
            Latest AI dispatch · {dispatchEntry.timestamp}
          </p>
          <pre className="floor-detail-panel__dispatch-msg">
            <BoldText text={dispatchEntry.message ?? ''} />
          </pre>
        </div>
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function FloorPlan() {
  const [dispatchMap,  setDispatchMap]  = useState({});   // sensor_id → latest dispatch entry
  const [sensorMap,    setSensorMap]    = useState({});   // sensor_id → latest raw reading
  const timerRef    = useRef(null);
  const lastDashRef = useRef(null);
  const lastSensRef = useRef(null);

  // ── Fetch dashboard_log.json ──────────────────────────────────────────────
  const fetchDispatch = useCallback(async () => {
    try {
      const res = await fetch('/log/dashboard_log.json');
      if (!res.ok) return;
      const text = await res.text();
      if (text === lastDashRef.current) return;
      lastDashRef.current = text;

      const entries = text
        .split('\n')
        .filter(Boolean)
        .map((l) => { try { return JSON.parse(l); } catch { return null; } })
        .filter(Boolean);

      // Keep only the most recent entry per sensor
      const map = {};
      for (const e of entries) {
        if (e.sensor_id) map[e.sensor_id] = e;
      }
      setDispatchMap(map);
    } catch { /* ignore */ }
  }, []);

  // ── Fetch sensor_log.json ─────────────────────────────────────────────────
  const fetchSensor = useCallback(async () => {
    try {
      const res = await fetch('/log/sensor_log.json');
      if (!res.ok) return;
      const text = await res.text();
      if (text === lastSensRef.current) return;
      lastSensRef.current = text;

      const entries = text
        .split('\n')
        .filter(Boolean)
        .map((l) => { try { return JSON.parse(l); } catch { return null; } })
        .filter(Boolean);

      const map = {};
      for (const e of entries) {
        if (e.sensor_id) map[e.sensor_id] = e;
      }
      setSensorMap(map);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchDispatch();
    fetchSensor();
    timerRef.current = setInterval(() => {
      fetchDispatch();
      fetchSensor();
    }, POLL_MS);
    return () => clearInterval(timerRef.current);
  }, [fetchDispatch, fetchSensor]);

  // ── Derive per-sensor status ──────────────────────────────────────────────
  const statusMap = useMemo(() => {
    const m = {};
    for (const node of SENSOR_NODES) {
      m[node.sensor_id] = deriveSensorStatus(node.sensor_id, dispatchMap, sensorMap);
    }
    return m;
  }, [dispatchMap, sensorMap]);

  // ── Zone-level status (worst sensor wins) ─────────────────────────────────
  const zoneStatusMap = useMemo(() => {
    const order = { critical: 3, warning: 2, ok: 1, unknown: 0 };
    const m = {};
    for (const zone of ZONES) {
      const sensors = SENSOR_NODES.filter((n) => n.zone === zone.id);
      const worst   = sensors.reduce((acc, n) => {
        const s = statusMap[n.sensor_id] ?? 'unknown';
        return order[s] > order[acc] ? s : acc;
      }, 'unknown');
      m[zone.id] = worst;
    }
    return m;
  }, [statusMap]);

  const hasData = Object.keys(dispatchMap).length > 0 || Object.keys(sensorMap).length > 0;

  return (
    <Grid>
      <Column lg={16} md={8} sm={4}>
        <div className="section-header" style={{ marginTop: '1.25rem' }}>
          <h2>Factory Floor Plan</h2>
          <p>
            Live sensor status for all zones. Updates every {POLL_MS / 1000} s.
          </p>
        </div>

        {/* Legend */}
        <div className="floor-legend">
          {[
            { status: 'ok',       label: 'All clear (INFO)' },
            { status: 'warning',  label: 'Warning threshold exceeded' },
            { status: 'critical', label: 'Critical — AI dispatch active' },
            { status: 'unknown',  label: 'No data yet' },
          ].map(({ status, label }) => (
            <span key={status} className="floor-legend__item">
              <span
                className="floor-legend__dot"
                style={{ background: STATUS_COLOURS[status] }}
                aria-hidden="true"
              />
              {label}
            </span>
          ))}
        </div>

        {!hasData && (
          <InlineNotification
            kind="info"
            title="Waiting for data"
            subtitle="Make sure the sensor producers and agent bridge are running."
            hideCloseButton
            style={{ marginBottom: '1rem' }}
          />
        )}
      </Column>

      {/* Floor plan SVG — always full width */}
      <Column lg={16} md={8} sm={4}>
        <div className="floor-plan-wrapper">
          <svg
            viewBox="0 0 800 480"
            className="floor-plan-svg"
            aria-label="Factory floor plan"
            role="img"
          >
            {/* Background grid */}
            <defs>
              <pattern id="fp-grid" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#3a3a3a" strokeWidth="0.5" />
              </pattern>
              {/* Glow filter for critical sensors */}
              <filter id="glow-crit" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="4" result="blur" />
                <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
              <filter id="glow-warn" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
            </defs>

            {/* Floor background */}
            <rect x="0" y="0" width="800" height="480" fill="#0f0f0f" />
            <rect x="0" y="0" width="800" height="480" fill="url(#fp-grid)" />

            {/* Floor outline / outer walls */}
            <rect x="40" y="50" width="720" height="340" rx={8} fill="none" stroke="#6f6f6f" strokeWidth="2" />

            {/* Corridor label */}
            <text x="400" y="430" textAnchor="middle" fill="#8d8d8d" fontSize="11" fontFamily="'IBM Plex Mono', monospace">
              MAIN CORRIDOR
            </text>
            <line x1="40" y1="415" x2="360" y2="415" stroke="#6f6f6f" strokeWidth="1" strokeDasharray="4 4" />
            <line x1="440" y1="415" x2="760" y2="415" stroke="#6f6f6f" strokeWidth="1" strokeDasharray="4 4" />

            {/* Zone divider */}
            <line x1="400" y1="50" x2="400" y2="390" stroke="#6f6f6f" strokeWidth="1.5" strokeDasharray="6 4" />
            <text x="400" y="68" textAnchor="middle" fill="#8d8d8d" fontSize="9" fontFamily="'IBM Plex Mono', monospace">
              PARTITION
            </text>

            {/* Entry/exit doors */}
            {/* Left door */}
            <rect x="40"  y="250" width="12" height="40" fill="#0f0f0f" stroke="#8d8d8d" strokeWidth="1" />
            <text x="38"  y="282" textAnchor="end" fill="#8d8d8d" fontSize="9" fontFamily="'IBM Plex Mono', monospace">EXIT</text>
            {/* Right door */}
            <rect x="748" y="250" width="12" height="40" fill="#0f0f0f" stroke="#8d8d8d" strokeWidth="1" />
            <text x="762" y="282" textAnchor="start" fill="#8d8d8d" fontSize="9" fontFamily="'IBM Plex Mono', monospace">EXIT</text>
            {/* Bottom door */}
            <rect x="376" y="378" width="48" height="12" fill="#0f0f0f" stroke="#8d8d8d" strokeWidth="1" />
            <text x="400" y="408" textAnchor="middle" fill="#8d8d8d" fontSize="9" fontFamily="'IBM Plex Mono', monospace">ENTRY</text>

            {/* Zone rectangles */}
            {ZONES.map((zone) => (
              <ZoneRect key={zone.id} zone={zone} zoneStatus={zoneStatusMap[zone.id]} />
            ))}

            {/* Ventilation ducts */}
            <rect x="60"  y="55"  width="280" height="18" rx={3} fill="#1c1c1c" stroke="#6f6f6f" strokeWidth="1" />
            <text x="200" y="67"  textAnchor="middle" fill="#8d8d8d" fontSize="8" fontFamily="'IBM Plex Mono', monospace">VENTILATION DUCT</text>
            <rect x="460" y="55"  width="270" height="18" rx={3} fill="#1c1c1c" stroke="#6f6f6f" strokeWidth="1" />
            <text x="595" y="67"  textAnchor="middle" fill="#8d8d8d" fontSize="8" fontFamily="'IBM Plex Mono', monospace">VENTILATION DUCT</text>

            {/* Sensor nodes — display only, no click interaction */}
            {SENSOR_NODES.map((node) => (
              <SensorNode
                key={node.sensor_id}
                node={node}
                status={statusMap[node.sensor_id] ?? 'unknown'}
                isSelected={false}
                onClick={() => {}}
              />
            ))}

            {/* Compass / north indicator */}
            <g transform="translate(755, 55)">
              <circle cx="0" cy="0" r="14" fill="#1c1c1c" stroke="#6f6f6f" strokeWidth="1" />
              <text x="0" y="-4"  textAnchor="middle" fill="#4589ff" fontSize="9" fontWeight="700">N</text>
              <line x1="0" y1="2" x2="0" y2="10" stroke="#4589ff" strokeWidth="1.5" />
            </g>

            {/* Scale bar */}
            <g transform="translate(60, 410)">
              <line x1="0" y1="0" x2="60" y2="0" stroke="#6f6f6f" strokeWidth="1.5" />
              <line x1="0" y1="-4" x2="0"  y2="4" stroke="#6f6f6f" strokeWidth="1.5" />
              <line x1="60" y1="-4" x2="60" y2="4" stroke="#6f6f6f" strokeWidth="1.5" />
              <text x="30" y="14" textAnchor="middle" fill="#8d8d8d" fontSize="9" fontFamily="'IBM Plex Mono', monospace">10 m</text>
            </g>
          </svg>
        </div>
      </Column>

      {/* Always-visible sensor detail cards — one per zone, side by side */}
      {SENSOR_NODES.map((node) => (
        <Column key={node.sensor_id} lg={8} md={4} sm={4}>
          <SensorDetail
            sensorId={node.sensor_id}
            status={statusMap[node.sensor_id] ?? 'unknown'}
            dispatchEntry={dispatchMap[node.sensor_id] ?? null}
            sensorReading={sensorMap[node.sensor_id] ?? null}
          />
        </Column>
      ))}
    </Grid>
  );
}
