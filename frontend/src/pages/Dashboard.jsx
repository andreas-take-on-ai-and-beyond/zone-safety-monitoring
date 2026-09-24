import React, { useMemo } from 'react';
import {
  Grid,
  Column,
  Tile,
  Tag,
  InlineNotification,
  Accordion,
  AccordionItem,
  Dropdown,
  Tabs,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
} from '@carbon/react';
import {
  WarningAltFilled,
  CheckmarkFilled,
} from '@carbon/icons-react';
import SensorTelemetry from './SensorTelemetry';
import FloorPlan from './FloorPlan';
import BoldText from '../components/BoldText';

// ─── Constants ────────────────────────────────────────────────────────────────
const DEPT_LABEL = {
  EHS: { icon: '☣', color: '#ff8800' },
  Mechanics: { icon: '⚙', color: '#4589ff' },
  Electrical: { icon: '⚡', color: '#a56eff' },
  Facilities: { icon: '🏢', color: '#42be65' },
};

function urgencyTagType(urgency) {
  return urgency === 'CRITICAL' ? 'red' : 'green';
}

const ZONE_COLOUR = {
  'ENV_SENSOR_ZONE_CNC':      '#a56eff',
  'ENV_SENSOR_ZONE_ASSEMBLY': '#4589ff',
};

function zoneLabel(sensor_id) {
  if (sensor_id === 'ENV_SENSOR_ZONE_CNC')      return 'CNC';
  if (sensor_id === 'ENV_SENSOR_ZONE_ASSEMBLY') return 'Electronics Assembly';
  return sensor_id;
}

function ZoneChip({ sensor_id }) {
  const bg = ZONE_COLOUR[sensor_id] ?? '#6f6f6f';
  return (
    <span style={{
      display:      'inline-flex',
      alignItems:   'center',
      padding:      '0 0.5rem',
      height:       '1.5rem',
      lineHeight:   1,
      borderRadius: '1rem',
      background:   bg,
      color:        '#ffffff',
      fontSize:     '0.75rem',
      fontWeight:   400,
      whiteSpace:   'nowrap',
      userSelect:   'none',
    }}>
      {zoneLabel(sensor_id)}
    </span>
  );
}

function deptTagType(dept) {
  const map = { EHS: 'orange', Mechanics: 'blue', Electrical: 'purple', Facilities: 'teal' };
  return map[dept] || 'gray';
}

// ─── KPI Tile ─────────────────────────────────────────────────────────────────
function KpiTile({ label, value, accentClass }) {
  return (
    <Tile className={`kpi-tile ${accentClass}`}>
      <p className="kpi-tile__label">{label}</p>
      <p className="kpi-tile__value">{value}</p>
    </Tile>
  );
}

// ─── Critical Alert Banner ────────────────────────────────────────────────────
function CriticalBanner({ entry }) {
  if (!entry) return null;
  const reasoning = entry.reasoning || entry.message || '';
  return (
    <div className="critical-banner" role="alert" aria-live="assertive">
      <div className="critical-banner__header">
        <WarningAltFilled size={20} aria-label="Critical" style={{ fill: 'var(--cds-support-error)' }} />
        <span className="critical-banner__title">Latest Critical Alert</span>
        <span className="critical-banner__meta">
          {entry.timestamp}
        </span>
      </div>
      <div style={{ marginBottom: '0.5rem' }}>
        <Tag type={deptTagType(entry.department)} size="sm">
          {entry.department}
        </Tag>
        <Tag type="red" size="sm">
          CRITICAL
        </Tag>
        <ZoneChip sensor_id={entry.sensor_id} />
      </div>
      <pre className="critical-banner__body"><BoldText text={reasoning} /></pre>
    </div>
  );
}

// ─── Dispatch Accordion Item ──────────────────────────────────────────────────
function DispatchItem({ entry }) {
  const { urgency, department, zone, sensor_id, timestamp, message, reasoning, env_report } = entry;

  const accordionTitle = (
    <span className="dispatch-accordion-title">
      <Tag type={urgencyTagType(urgency)} size="sm">
        {urgency}
      </Tag>
      <Tag type={deptTagType(department)} size="sm">
        {department}
      </Tag>
      <ZoneChip sensor_id={sensor_id} />
      <span style={{ color: 'var(--cds-text-secondary)', fontSize: '0.8125rem' }}>
        {timestamp}
      </span>
    </span>
  );

  return (
    <AccordionItem title={accordionTitle}>
      <p className="dispatch-section-label">Technician action</p>
      <pre className="dispatch-message"><BoldText text={message} /></pre>

      {reasoning && reasoning !== message && (
        <>
          <p className="dispatch-section-label">AI reasoning (full LLM output)</p>
          <pre className="reasoning-block"><BoldText text={reasoning} /></pre>
        </>
      )}

      {env_report && (
        <>
          <p className="dispatch-section-label">Sensor assessment (tool output)</p>
          <pre className="env-block">{env_report}</pre>
        </>
      )}
    </AccordionItem>
  );
}

// ─── AI Dispatches tab content ────────────────────────────────────────────────
function DispatchesTab({ df }) {
  const knownSensors = useMemo(() => {
    const SENSOR_ORDER = ['ENV_SENSOR_ZONE_CNC', 'ENV_SENSOR_ZONE_ASSEMBLY'];
    const all = [...new Set(df.map((r) => r.sensor_id))];
    return all.sort((a, b) => {
      const ia = SENSOR_ORDER.indexOf(a);
      const ib = SENSOR_ORDER.indexOf(b);
      if (ia === -1 && ib === -1) return a.localeCompare(b);
      if (ia === -1) return 1;
      if (ib === -1) return -1;
      return ia - ib;
    });
  }, [df]);
  const [selectedZone, setSelectedZone] = React.useState('All');

  const criticalCount  = df.filter((r) => r.urgency === 'CRITICAL').length;
  const infoCount      = df.filter((r) => r.urgency === 'INFO').length;
  const latestCritical = df.filter((r) => r.urgency === 'CRITICAL').at(-1);

  const filtered  = selectedZone === 'All' ? df : df.filter((r) => r.sensor_id === selectedZone);
  const reversed  = [...filtered].reverse().slice(0, 20);
  const zoneItems = [{ id: 'All', label: 'All zones' }, ...knownSensors.map((s) => ({ id: s, label: s }))];

  if (df.length === 0) {
    return (
      <InlineNotification
        kind="info"
        title="Waiting for data"
        subtitle="No zone alerts received yet. Make sure the Kafka stream and agent bridge are running."
        hideCloseButton
        style={{ marginTop: '1rem' }}
      />
    );
  }

  return (
    <Grid>
      {/* ── KPI Row ───────────────────────────────────────────────── */}
      <Column lg={16} md={8} sm={4}>
        <div className="section-header" style={{ marginTop: '1.25rem' }}>
          <h2>Overview</h2>
          <p>AI-powered multi-zone environmental monitoring — CNC Machining &amp; Electronics Assembly</p>
        </div>
      </Column>

      <Column lg={4} md={2} sm={2}>
        <KpiTile label="Total Dispatches" value={df.length} accentClass="kpi-tile--info" />
      </Column>
      <Column lg={4} md={2} sm={2}>
        <KpiTile label="Critical" value={criticalCount} accentClass="kpi-tile--critical" />
      </Column>
      <Column lg={4} md={2} sm={2}>
        <KpiTile label="Info" value={infoCount} accentClass="kpi-tile--success" />
      </Column>
      <Column lg={4} md={2} sm={2}>
        <KpiTile label="Active Zones" value={knownSensors.length} accentClass="kpi-tile--warning" />
      </Column>

      {/* ── Zone Breakdown ────────────────────────────────────────── */}
      <Column lg={16} md={8} sm={4}>
        <hr className="section-divider" aria-hidden="true" />
        <div className="section-header">
          <h2>Breakdown by Zone</h2>
        </div>
        <div className="zone-grid">
          {knownSensors.map((sid) => {
            const s        = df.filter((r) => r.sensor_id === sid);
            const zoneName = s[0]?.zone ?? sid;
            const crit     = s.filter((r) => r.urgency === 'CRITICAL').length;
            const info     = s.filter((r) => r.urgency === 'INFO').length;
            return (
              <div key={sid} className="zone-card">
                <p className="zone-card__name">{zoneName.replace(/_/g, ' ')}</p>
                <p className="zone-card__id">{sid}</p>
                <div className="zone-card__counts">
                  <div className="zone-card__count">
                    <span style={{ color: 'var(--cds-support-error)' }}>{crit}</span>
                    <span>Critical</span>
                  </div>
                  <div className="zone-card__count">
                    <span style={{ color: 'var(--cds-support-success)' }}>{info}</span>
                    <span>Info</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </Column>

      {/* ── Department Breakdown ──────────────────────────────────── */}
      <Column lg={16} md={8} sm={4}>
        <hr className="section-divider" aria-hidden="true" />
        <div className="section-header">
          <h2>Breakdown by Department</h2>
        </div>
        <div className="dept-grid">
          {Object.keys(DEPT_LABEL).map((dept) => {
            const { icon }   = DEPT_LABEL[dept];
            const deptRows   = df.filter((r) => r.department?.toLowerCase() === dept.toLowerCase());
            const crit       = deptRows.filter((r) => r.urgency === 'CRITICAL').length;
            const info       = deptRows.filter((r) => r.urgency === 'INFO').length;
            return (
              <div key={dept} className="dept-card">
                <p className="dept-card__name">
                  {dept}
                </p>
                <div className="dept-card__counts">
                  <div className="dept-card__count">
                    <span style={{ color: 'var(--cds-support-error)' }}>{crit}</span>
                    <span>Critical</span>
                  </div>
                  <div className="dept-card__count">
                    <span style={{ color: 'var(--cds-support-success)' }}>{info}</span>
                    <span>Info</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </Column>

      {/* ── Critical Alert Banner ─────────────────────────────────── */}
      {latestCritical && (
        <Column lg={16} md={8} sm={4}>
          <hr className="section-divider" aria-hidden="true" />
          <div className="section-header">
            <h2>Latest Critical Alert</h2>
          </div>
          <CriticalBanner entry={latestCritical} />
        </Column>
      )}

      {/* ── Dispatch History ──────────────────────────────────────── */}
      <Column lg={16} md={8} sm={4}>
        <hr className="section-divider" aria-hidden="true" />
        <div className="section-header">
          <h2>Latest AI Dispatches</h2>
          <p>
            Each dispatch shows the technician action recommended by the AI agent. Expand a row to
            see the full LLM reasoning and the environmental sensor assessment.
          </p>
        </div>

        <div style={{ maxWidth: '400px', marginBottom: '1.5rem' }}>
          <Dropdown
            id="zone-filter"
            titleText="Filter by zone"
            label="All zones"
            items={zoneItems}
            itemToString={(item) => (item ? item.label : '')}
            selectedItem={zoneItems.find((i) => i.id === selectedZone) ?? zoneItems[0]}
            onChange={({ selectedItem }) => setSelectedZone(selectedItem?.id ?? 'All')}
          />
        </div>

        {reversed.length === 0 ? (
          <div className="waiting-state">
            <CheckmarkFilled size={32} style={{ fill: 'var(--cds-text-secondary)' }} aria-hidden="true" />
            <p>No dispatches match this filter.</p>
          </div>
        ) : (
          <Accordion align="start">
            {reversed.map((entry, idx) => (
              <DispatchItem key={`${entry.timestamp}-${entry.sensor_id}-${idx}`} entry={entry} />
            ))}
          </Accordion>
        )}
      </Column>
    </Grid>
  );
}

// ─── Main page — tabbed shell ─────────────────────────────────────────────────
export default function Dashboard({ data }) {
  const df = useMemo(() => {
    return data.map((row) => ({
      department: 'General',
      sensor_id:  'UNKNOWN',
      zone:       'UNKNOWN',
      message:    '',
      ...row,
      reasoning:  row.reasoning  ?? '',
      env_report: row.env_report ?? '',
    }));
  }, [data]);

  return (
    <div className="dashboard-tabs-wrapper">
      <Tabs>
        <TabList aria-label="Dashboard views" contained>
          <Tab>AI Dispatches</Tab>
          <Tab>Sensor Telemetry</Tab>
          <Tab>Floor Plan</Tab>
        </TabList>
        <TabPanels>
          <TabPanel>
            <DispatchesTab df={df} />
          </TabPanel>
          <TabPanel>
            <SensorTelemetry />
          </TabPanel>
          <TabPanel>
            <FloorPlan />
          </TabPanel>
        </TabPanels>
      </Tabs>
    </div>
  );
}
