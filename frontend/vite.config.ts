import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// localhost:8000 for running the backend directly on the host (day-to-day dev);
// docker-compose overrides this to http://backend:8000 for the containerized stack.
// 127.0.0.1, not "localhost" — Node can resolve "localhost" to the IPv6 ::1
// on some setups, and the backend dev server binds only to the IPv4 address.
const apiProxyTarget = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // Docker Desktop on Windows doesn't reliably forward native filesystem
    // change events across a bind mount, so chokidar's default watcher misses
    // edits entirely until the container restarts. Polling is a bit more CPU
    // but is what actually works in that environment; harmless on Linux/Mac.
    watch: { usePolling: true },
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
