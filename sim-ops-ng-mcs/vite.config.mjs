import { fileURLToPath, URL } from "url";

import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import pkg from "./package.json" with { type: "json" };

// https://vitejs.dev/config/
export default defineConfig({
  // env from the repo root .env; in Docker that's empty, so VITE_* come from the process env (Dockerfile.nginx)
  envDir: "..",
  plugins: [vue()],
  define: {
    // Project version (kept in sync with the root VERSION by bin/version.sh)
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  optimizeDeps: {
    exclude: ['vue-demi']
	},
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
  },
});
