import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __dirname       = path.dirname(fileURLToPath(import.meta.url));
const ROOT            = path.resolve(__dirname, '..');
const LOG_FILE        = path.resolve(ROOT, 'dashboard_log.json');
const SENSOR_LOG_FILE = path.resolve(ROOT, 'sensor_log.json');

/**
 * Vite dev-server middleware: serves both log files from the repo root
 * at /log/*.json — without any caching.
 */
function serveLogFiles() {
  function sendFile(filePath, res) {
    if (!fs.existsSync(filePath)) {
      res.writeHead(404);
      res.end('');
      return;
    }
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    res.end(fs.readFileSync(filePath, 'utf-8'));
  }

  return {
    name: 'serve-log-files',
    configureServer(server) {
      server.middlewares.use('/log/dashboard_log.json', (_req, res) => sendFile(LOG_FILE, res));
      server.middlewares.use('/log/sensor_log.json',    (_req, res) => sendFile(SENSOR_LOG_FILE, res));
    },
  };
}

export default defineConfig({
  plugins: [react(), serveLogFiles()],
  css: {
    preprocessorOptions: {
      scss: {
        silenceDeprecations: ['legacy-js-api'],
      },
    },
  },
  server: {
    port: 4173,
  },
});
