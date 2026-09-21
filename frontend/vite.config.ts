import { reactRouter } from "@react-router/dev/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

// Local development only: the FastAPI backend's default `uvicorn` port.
// Read from a plain (non-`VITE_`-prefixed) environment variable so it
// configures the Vite dev server process itself (Node-side) and is
// never bundled into client-side JavaScript -- see
// frontend/.env.example for the client-visible base-URL setting.
const BACKEND_PROXY_TARGET = process.env.BACKEND_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [reactRouter(), tailwindcss()],
  server: {
    proxy: {
      // Frontend code calls relative paths like `/api/v1/...`; the dev
      // server forwards them to the local FastAPI backend, so no
      // hostname is ever hardcoded in application code.
      "/api": {
        target: BACKEND_PROXY_TARGET,
        changeOrigin: true,
      },
    },
  },
});
