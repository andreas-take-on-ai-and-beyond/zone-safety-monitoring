/**
 * SensorTelemetry.jsx
 *
 * Second dashboard — real-time sensor telemetry.
 * Polls /log/sensor_log.json every 3 s and renders one SVG line chart
 * per metric (temperature, humidity, CO₂, CO, PM2.5).
 * Each chart shows a separate coloured series per sensor/zone.
 *
 * No extra npm dependencies — pure SVG drawn with React, styled with
 * Carbon design tokens (g90 dark theme).
 */

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  Grid,
  Column,
  Tile,
  Tag,
  InlineNotification,
  SkeletonText,
  ToastNotification,
} from '@carbon/react';

// ── Colour palette — IBM data-vis colours, g90-friendly ───────────────────────
// Index 0 = CNC (blue), index 1 = Assembly (purple), more if zones are added
const SERIES_COLOURS = [
  '#4589ff', // Blue 40
  '#a56eff', // Purple 40
  '#3ddbd9', // Teal 30
  '#ff832b', // Orange 40
  '#42be65', // Green 40
  '#fa4d56', // Red 40
];

// ── Metric definitions ─────────────────────────────────────────────────────────
// Metric definitions for the telemetry line charts.
//
// Humidity is a DUAL-DIRECTION metric: the safe operating window is 30–60 %.
//   Below 30 % → ESD risk (ANSI/ESD S20.20)
//   Above 60 % → condensation / solder oxidation risk
// The chart renders warnLow/warnHigh as dashed reference lines marking the
// safe band. statusColour uses custom logic: green inside the band, yellow
// outside it. A single warn/crit pair (warn=30) would make 45 % "warning"
// because 45 >= 30 — that is wrong for a window metric.
//
// Pressure is NOT shown: it carries no actionable safety information in this
// pipeline (Flink doesn't threshold it, the agent doesn't use it, the floor
// plan doesn't check it). Removing it keeps the telemetry screen clean.
//
const METRICS = [
  {
    key: 'temperature_c',
    label: 'Temperature',
    unit: '°C',
    // CNC upper bound — Assembly warn is 23 °C but both zones share this chart
    thresholds: { warn: 28.5, crit: 38.0 },
    yMin: 18,
    yMax: 52,
  },
  {
    key: 'humidity_pct',
    label: 'Humidity',
    unit: '%',
    // Dual-direction window: safe band is 30–60 %.
    // warnLow / warnHigh mark the edges; statusColour is green inside the band.
    thresholds: null,          // disable the standard ≥warn logic for this metric
    warnLow:  30,              // below this → ESD risk (ANSI/ESD S20.20)
    warnHigh: 60,              // above this → condensation / solder oxidation
    yMin: 10,
    yMax: 100,
  },
  {
    key: 'co2_ppm',
    label: 'CO₂',
    unit: ' ppm',
    thresholds: { warn: 1000, crit: 1500 },
    yMin: 350,
    yMax: 2000,
  },
  {
    key: 'co_ppm',
    label: 'CO',
    unit: ' ppm',
    // warn 8 ppm (tramp oil / flux trace), crit 15 ppm (early fire signal)
    thresholds: { warn: 8, crit: 15 },
    yMin: 0,
    yMax: 40,
  },
  {
    key: 'pm25_ugm3',
    label: 'PM2.5',
    unit: ' µg/m³',
    // CNC upper bound: warn 25 (coolant mist ok), crit 35 (WHO 24h limit)
    thresholds: { warn: 25, crit: 35 },
    yMin: 0,
    yMax: 100,
  },
];

// ── Helpers ────────────────────────────────────────────────────────────────────
/** Map a value in [yMin, yMax] → SVG y coordinate in [paddingT, height-paddingB] */
function toY(val, yMin, yMax, h, padT, padB) {
  const frac = (val - yMin) / (yMax - yMin);
  return h - padB - frac * (h - padT - padB);
}

/** Map a series index to x coordinate */
function toX(idx, total, w, padL, padR) {
  if (total <= 1) return padL;
  return padL + (idx / (total - 1)) * (w - padL - padR);
}

/** Build an SVG polyline `points` string from an array of [x, y] pairs */
function toPoints(pairs) {
  return pairs.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
}

// ── SVG line chart component ───────────────────────────────────────────────────
const CHART_W   = 460;
const CHART_H   = 180;
const PAD_L     = 48;
const PAD_R     = 12;
const PAD_T     = 14;
const PAD_B     = 32;
const Y_TICKS   = 5;

function LineChart({ metric, seriesData, sensorIds, colourMap }) {
  const { key, label, unit, thresholds, warnLow, warnHigh, yMin, yMax } = metric;
  const isWindowMetric = (warnLow != null || warnHigh != null);

  // Y axis ticks
  const yTicks = useMemo(() => {
    const ticks = [];
    for (let i = 0; i <= Y_TICKS; i++) {
      const val = yMin + (i / Y_TICKS) * (yMax - yMin);
      const y   = toY(val, yMin, yMax, CHART_H, PAD_T, PAD_B);
      ticks.push({ val: Math.round(val), y });
    }
    return ticks;
  }, [yMin, yMax]);

  // Latest value per sensor (for the legend)
  const latestValues = useMemo(() => {
    return sensorIds.map((sid) => {
      const pts = seriesData[sid] ?? [];
      return pts.length > 0 ? pts[pts.length - 1][key] : null;
    });
  }, [sensorIds, seriesData, key]);

  // Build polylines per sensor
  const polylines = useMemo(() => {
    return sensorIds.map((sid) => {
      const pts = seriesData[sid] ?? [];
      if (pts.length < 2) return null;
      const pairs = pts.map((p, i) => [
        toX(i, pts.length, CHART_W, PAD_L, PAD_R),
        toY(
          Math.max(yMin, Math.min(yMax, p[key] ?? yMin)),
          yMin, yMax, CHART_H, PAD_T, PAD_B
        ),
      ]);
      return { sid, colour: colourMap[sid], points: toPoints(pairs) };
    }).filter(Boolean);
  }, [sensorIds, seriesData, key, yMin, yMax, colourMap]);

  // Threshold / reference lines
  // Standard metrics: warn (yellow dashed) + crit (red dashed)
  // Window metrics (humidity): warnLow + warnHigh both shown as yellow dashed,
  //   labelled "Low" and "High" — they mark the safe band edges, not breaches.
  const thresholdLines = useMemo(() => {
    if (isWindowMetric) {
      const lines = [];
      if (warnLow  != null) lines.push({ val: warnLow,  colour: '#f1c21b', dash: '4 3', lbl: 'Low' });
      if (warnHigh != null) lines.push({ val: warnHigh, colour: '#f1c21b', dash: '4 3', lbl: 'High' });
      return lines.map(({ val, colour, dash, lbl }) => ({
        y: toY(val, yMin, yMax, CHART_H, PAD_T, PAD_B),
        colour, dash, lbl,
      }));
    }
    if (!thresholds) return [];
    return [
      { val: thresholds.warn, colour: '#f1c21b', dash: '4 3', lbl: 'Warn' },
      { val: thresholds.crit, colour: '#fa4d56', dash: '4 2', lbl: 'Crit' },
    ].map(({ val, colour, dash, lbl }) => ({
      y: toY(val, yMin, yMax, CHART_H, PAD_T, PAD_B),
      colour, dash, lbl,
    }));
  }, [thresholds, isWindowMetric, warnLow, warnHigh, yMin, yMax]);

  // Top-border status colour
  // Standard:      green below warn / yellow below crit / red at/above crit
  // Window metric: green inside band / yellow outside band
  const statusColour = useMemo(() => {
    const vals = latestValues.filter((v) => v !== null);
    if (vals.length === 0) return 'var(--cds-support-info)';

    if (isWindowMetric) {
      const outsideBand = vals.some(
        (v) => (warnLow != null && v < warnLow) || (warnHigh != null && v > warnHigh)
      );
      return outsideBand ? 'var(--cds-support-warning)' : 'var(--cds-support-success)';
    }

    if (!thresholds) return 'var(--cds-support-info)';
    if (vals.some((v) => v >= thresholds.crit)) return 'var(--cds-support-error)';
    if (vals.some((v) => v >= thresholds.warn)) return 'var(--cds-support-warning)';
    return 'var(--cds-support-success)';
  }, [thresholds, isWindowMetric, warnLow, warnHigh, latestValues]);

  return (
    <Tile className="sensor-chart-tile" style={{ '--chart-accent': statusColour }}>
      {/* Header row */}
      <div className="sensor-chart__header">
        <span className="sensor-chart__title">{label}</span>
        <div className="sensor-chart__legend">
          {sensorIds.map((sid, sIdx) => (
            <span key={sid} className="sensor-chart__legend-item">
              <span
                className="sensor-chart__legend-dot"
                style={{ background: colourMap[sid] }}
                aria-hidden="true"
              />
              <span className="sensor-chart__legend-name">
                {sid.replace('ENV_SENSOR_ZONE_', '')}
              </span>
              {latestValues[sIdx] !== null && (
                <span className="sensor-chart__legend-val">
                  {Number(latestValues[sIdx]).toFixed(2)}{unit}
                </span>
              )}
            </span>
          ))}
        </div>
      </div>

      {/* SVG chart */}
      <svg
        viewBox={`0 0 ${CHART_W} ${CHART_H}`}
        aria-label={`${label} over time`}
        role="img"
        className="sensor-chart__svg"
      >
        {/* Y grid + tick labels */}
        {yTicks.map(({ val, y }) => (
          <g key={val}>
            <line
              x1={PAD_L} y1={y} x2={CHART_W - PAD_R} y2={y}
              stroke="var(--cds-border-subtle-01)"
              strokeWidth="0.5"
            />
            <text
              x={PAD_L - 4} y={y + 3.5}
              textAnchor="end"
              fill="var(--cds-text-secondary)"
              fontSize="9"
            >
              {val}
            </text>
          </g>
        ))}

        {/* Safe-band fill for window metrics (humidity) — green rect between warnLow and warnHigh */}
        {isWindowMetric && warnLow != null && warnHigh != null && (() => {
          const yTop = toY(warnHigh, yMin, yMax, CHART_H, PAD_T, PAD_B);
          const yBot = toY(warnLow,  yMin, yMax, CHART_H, PAD_T, PAD_B);
          return (
            <rect
              x={PAD_L} y={yTop}
              width={CHART_W - PAD_L - PAD_R}
              height={yBot - yTop}
              fill="#42be65"
              opacity="0.06"
            />
          );
        })()}

        {/* Threshold lines */}
        {thresholdLines.map(({ y, colour, dash, lbl }) => (
          <g key={lbl}>
            <line
              x1={PAD_L} y1={y} x2={CHART_W - PAD_R} y2={y}
              stroke={colour}
              strokeWidth="1"
              strokeDasharray={dash}
              opacity="0.8"
            />
            <text
              x={CHART_W - PAD_R + 2} y={y + 3}
              fill={colour}
              fontSize="8"
            >
              {lbl}
            </text>
          </g>
        ))}

        {/* Data polylines */}
        {polylines.map(({ sid, colour, points }) => (
          <polyline
            key={sid}
            points={points}
            fill="none"
            stroke={colour}
            strokeWidth="1.8"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}

        {/* X axis base line */}
        <line
          x1={PAD_L} y1={CHART_H - PAD_B}
          x2={CHART_W - PAD_R} y2={CHART_H - PAD_B}
          stroke="var(--cds-border-subtle-01)"
          strokeWidth="1"
        />
      </svg>
    </Tile>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
const POLL_MS      = 3000;
const MAX_POINTS   = 80;   // last ~7 minutes at 5-second sensor intervals
const TOAST_TTL_MS = 5000; // new-alert toast auto-dismiss after 5 seconds


export default function SensorTelemetry() {
  const [rows,      setRows]      = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState(false);
  const lastTextRef    = useRef(null);
  const timerRef       = useRef(null);

  // ── New-dispatch alert state (must be declared before any early return) ────
  const [dispatchAlert,  setDispatchAlert]  = useState(null);
  const [toastVisible,   setToastVisible]   = useState(false);
  const dispatchCountRef = useRef(null);
  const toastTimerRef    = useRef(null);

  const fetchSensorLog = useCallback(async () => {
    try {
      const res = await fetch('/log/sensor_log.json');
      if (!res.ok) { setError(true); return; }
      const text = await res.text();
      if (text === lastTextRef.current) return;
      lastTextRef.current = text;

      const entries = text
        .split('\n')
        .filter(Boolean)
        .slice(-MAX_POINTS * 6)          // keep enough for all sensors
        .map((l) => { try { return JSON.parse(l); } catch { return null; } })
        .filter(Boolean);

      setRows(entries);
      setLoading(false);
      setError(false);
    } catch {
      setError(true);
    }
  }, []);

  // Lightweight poll for dashboard_log — detects new dispatches while on this tab
  const fetchDispatchLog = useCallback(async () => {
    try {
      const res = await fetch('/log/dashboard_log.json');
      if (!res.ok) return;
      const text = await res.text();
      const lines = text.split('\n').filter(Boolean);
      const count = lines.length;

      if (dispatchCountRef.current === null) {
        dispatchCountRef.current = count; // initialise baseline silently
        return;
      }

      if (count > dispatchCountRef.current) {
        const latest = (() => {
          try { return JSON.parse(lines[lines.length - 1]); } catch { return null; }
        })();
        dispatchCountRef.current = count;
        if (latest) {
          setDispatchAlert({
            urgency:   latest.urgency   ?? 'ALERT',
            zone:      latest.zone      ?? '',
            sensor:    latest.sensor_id ?? '',
            timestamp: latest.timestamp ?? '',
          });
          setToastVisible(true);
          clearTimeout(toastTimerRef.current);
          toastTimerRef.current = setTimeout(() => setToastVisible(false), TOAST_TTL_MS);
        }
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchSensorLog();
    fetchDispatchLog();
    timerRef.current = setInterval(() => {
      fetchSensorLog();
      fetchDispatchLog();
    }, POLL_MS);
    return () => {
      clearInterval(timerRef.current);
      clearTimeout(toastTimerRef.current);
    };
  }, [fetchSensorLog, fetchDispatchLog]);

  // Derive per-sensor series — last MAX_POINTS ticks per sensor
  const { sensorIds, seriesData, colourMap } = useMemo(() => {
    const SENSOR_ORDER = ['ENV_SENSOR_ZONE_CNC', 'ENV_SENSOR_ZONE_ASSEMBLY'];
    const ids = [...new Set(rows.map((r) => r.sensor_id))].sort((a, b) => {
      const ia = SENSOR_ORDER.indexOf(a);
      const ib = SENSOR_ORDER.indexOf(b);
      if (ia === -1 && ib === -1) return a.localeCompare(b);
      if (ia === -1) return 1;
      if (ib === -1) return -1;
      return ia - ib;
    });
    // Pin known sensors to stable colours so legend chips and chart lines always match.
    // CNC → index 0 (purple/pink), Assembly → index 1 (blue) — explicit order above.
    const PINNED = {
      'ENV_SENSOR_ZONE_CNC':      SERIES_COLOURS[1],
      'ENV_SENSOR_ZONE_ASSEMBLY': SERIES_COLOURS[0],
    };
    const cmap = Object.fromEntries(ids.map((id, i) => [id, PINNED[id] ?? SERIES_COLOURS[i % SERIES_COLOURS.length]]));
    const data = Object.fromEntries(
      ids.map((id) => [id, rows.filter((r) => r.sensor_id === id).slice(-MAX_POINTS)])
    );
    return { sensorIds: ids, seriesData: data, colourMap: cmap };
  }, [rows]);

  // ── Empty / loading states ─────────────────────────────────────────────────
  if (loading && !error) {
    return (
      <Grid>
        <Column lg={16} md={8} sm={4}>
          <div className="section-header" style={{ marginTop: '1rem' }}>
            <h2>Sensor Telemetry</h2>
            <p>Waiting for real-time sensor data…</p>
          </div>
          <div className="telemetry-chart-grid">
            {METRICS.map((m) => (
              <Tile key={m.key} className="sensor-chart-tile">
                <SkeletonText heading width="40%" />
                <SkeletonText paragraph lineCount={4} />
              </Tile>
            ))}
          </div>
        </Column>
      </Grid>
    );
  }

  if (error || rows.length === 0) {
    return (
      <Grid>
        <Column lg={16} md={8} sm={4}>
          <InlineNotification
            kind="warning"
            title="No sensor data"
            subtitle="sensor_log.json not found or empty. Make sure the agent bridge is running and sensor producers are active."
            hideCloseButton
          />
        </Column>
      </Grid>
    );
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <Grid>
      {/* ── New-dispatch toast ──────────────────────────────────────────────── */}
      {toastVisible && dispatchAlert && (
        <Column lg={16} md={8} sm={4}>
          <div className="dispatch-toast-wrapper" aria-live="assertive">
            <ToastNotification
              kind={dispatchAlert.urgency === 'CRITICAL' ? 'error' : 'warning'}
              title={`New AI dispatch — ${dispatchAlert.urgency}`}
              subtitle={`${dispatchAlert.zone.replace(/_/g, ' ')} · ${dispatchAlert.sensor} · ${dispatchAlert.timestamp} — switch to the AI Dispatches tab for details.`}
              caption=""
              timeout={TOAST_TTL_MS}
              onClose={() => setToastVisible(false)}
              lowContrast
            />
          </div>
        </Column>
      )}

      {/* Page header */}
      <Column lg={16} md={8} sm={4}>
        <div className="section-header" style={{ marginTop: '1rem' }}>
          <h2>Sensor Telemetry</h2>
          <p>
            Live readings from {sensorIds.length} zone sensor{sensorIds.length !== 1 ? 's' : ''} ·
            Updating every {POLL_MS / 1000} s · Last {MAX_POINTS} ticks per sensor shown
          </p>
        </div>

        {/* Zone legend chips — background pinned to the same colour as the chart line */}
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
          {sensorIds.map((sid) => (
            <span
              key={sid}
              style={{
                display:         'inline-flex',
                alignItems:      'center',
                padding:         '0 0.75rem',
                height:          '1.75rem',
                borderRadius:    '1rem',
                background:      colourMap[sid],
                color:           '#ffffff',
                fontSize:        '0.75rem',
                fontFamily:      'IBM Plex Mono, monospace',
                fontWeight:      600,
                letterSpacing:   '0.04em',
                userSelect:      'none',
              }}
            >
              {sid.replace('ENV_SENSOR_ZONE_', '')}
            </span>
          ))}
        </div>
      </Column>

      {/* Chart grid — 2 per row on large screens */}
      <Column lg={16} md={8} sm={4}>
        <div className="telemetry-chart-grid">
          {METRICS.map((metric) => (
            <LineChart
              key={metric.key}
              metric={metric}
              seriesData={seriesData}
              sensorIds={sensorIds}
              colourMap={colourMap}
            />
          ))}
        </div>
      </Column>
    </Grid>
  );
}
