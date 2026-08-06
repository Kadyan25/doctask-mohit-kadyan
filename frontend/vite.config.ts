import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// localhost:8000 for running the backend directly on the host (day-to-day dev);
// docker-compose overrides this to http://backend:8000 for the containerized stack.
const apiProxyTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
