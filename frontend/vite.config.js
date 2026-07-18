import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxy API requests to the FastAPI backend during development
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        secure: false,
        ws: true,          // proxy WebSocket upgrades too
      },
      "/health": {
        target: "http://localhost:8000",
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    // Production build optimizations
    sourcemap: false,
    rollupOptions: {
      output: {
        // Code splitting by vendor for better caching
        manualChunks(id) {
          if (id.includes("node_modules")) {
            if (id.includes("react-dom") || id.includes("react-router")) {
              return "vendor";
            }
            if (id.includes("@mui")) {
              return "mui";
            }
            if (id.includes("recharts") || id.includes("d3-")) {
              return "charts";
            }
          }
        },
      },
    },
  },
});
