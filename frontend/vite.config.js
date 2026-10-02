import { defineConfig } from "vite";

export default defineConfig(({ command }) => ({
  // In development Vite proxies API calls to FastAPI. Set VITE_ASSET_BASE=/ when
  // deploying the frontend as a Render Static Site. The default keeps the
  // combined FastAPI + frontend deployment working from /static/dist/.
  base: command === "build" ? (process.env.VITE_ASSET_BASE || "/static/dist/") : "/",
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
