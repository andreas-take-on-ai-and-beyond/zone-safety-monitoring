// Minimal express server that:
//   1. Serves the Carbon React SPA from frontend/dist
//   2. Exposes the log file at /log/dashboard_log.json (live reload-friendly)
//
// Run with:  node server.cjs
// Or in dev: Vite's dev server proxies /log/** directly (see vite.config.js)

const express = require('express');
const path    = require('path');
const fs      = require('fs');

const PORT            = process.env.PORT || 4173;
const LOG_FILE        = path.resolve(__dirname, 'dashboard_log.json');
const SENSOR_LOG_FILE = path.resolve(__dirname, 'sensor_log.json');
const DIST            = path.resolve(__dirname, 'frontend', 'dist');

const app = express();

// Serve log files (always fresh — no caching)
function serveJsonLog(file) {
  return (req, res) => {
    if (!fs.existsSync(file)) {
      return res.status(404).json({ error: 'Log file not found' });
    }
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    res.sendFile(file);
  };
}

app.get('/log/dashboard_log.json', serveJsonLog(LOG_FILE));
app.get('/log/sensor_log.json',    serveJsonLog(SENSOR_LOG_FILE));

// Serve the built SPA
app.use(express.static(DIST));
// Express 5 requires explicit wildcard syntax — '/{*splat}' replaces '*'
app.get('/{*splat}', (_req, res) => {
  res.sendFile(path.join(DIST, 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Zone Safety Dashboard running at http://localhost:${PORT}`);
});
