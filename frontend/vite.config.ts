import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      // Proxy API calls to the FastAPI backend during development.
      // API_TARGET defaults to localhost for running outside Docker;
      // docker-compose sets it to http://api:8001 (the service name).
      "/api": {
        target: process.env.API_TARGET ?? "http://localhost:8001",
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
