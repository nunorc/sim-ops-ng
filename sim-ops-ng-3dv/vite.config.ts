import { defineConfig } from 'vite';
import cesium from 'vite-plugin-cesium';
import pkg from './package.json' with { type: 'json' };

// '/3dv/' base only in production: in dev vite-plugin-cesium's middleware needs '/' to serve /cesium/Cesium.js
export default defineConfig(({ command }) => ({
  plugins: [cesium()],
  define: {
    // Project version (kept in sync with the root VERSION by bin/version.sh)
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  // env from the repo root .env; in Docker that's empty, so VITE_* come from the process env (Dockerfile.3dv)
  envDir: '..',
  base: command === 'build' ? '/3dv/' : '/',
  server: {
    port: 5174,
  },
}));
