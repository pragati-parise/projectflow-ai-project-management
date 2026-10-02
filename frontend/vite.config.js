import { defineConfig } from "vite";

export default defineConfig(({ command }) => ({
  // In development the browser talks to Vite; Vite forwards API calls to FastAPI.
  // In production the built files are served by FastAPI from /static/dist/.
  base: command === "build" ? "/static/dist/" : "/",
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/auth": "http://127.0.0.1:8000",
      "/projects": "http://127.0.0.1:8000",
      "/tasks": "http://127.0.0.1:8000",
      "/ai": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
  build: {
    outDir: "../static/dist",
    emptyOutDir: true,
  },
}));
