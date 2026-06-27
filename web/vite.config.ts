import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { mockBackendPlugin } from "./dev/mockBackend";

export default defineConfig(({ command }) => ({
  plugins: [vue(), command === "serve" && mockBackendPlugin()].filter(Boolean),
  server: {
    host: "127.0.0.1",
    port: 5173,
  },
  build: {
    outDir: "../proxy/gsloc_proxy/static",
    emptyOutDir: true,
  },
}));
