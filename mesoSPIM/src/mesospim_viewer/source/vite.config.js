import { defineConfig } from "vite";
import { neuroglancerForQt } from "./scripts/neuroglancer.mjs";

export default defineConfig({
  // Compiles the engine's workers and applies its few edits while building,
  // leaving node_modules as npm installed it (scripts/neuroglancer.mjs).
  plugins: [neuroglancerForQt()],
  build: {
    // Into the Python package, so that `pip install` ships the page with it.
    outDir: "../build",
    emptyOutDir: true,
    // The engine's background worker must be a real file, never a data: URL:
    // a data:-URL worker has no origin, so the absolute-path fetches it makes
    // for image chunks cannot resolve.
    assetsInlineLimit: 0,
    // The Data viewer window is Qt WebEngine 5.15, Chromium 83: newer syntax is
    // rewritten for it. Newer browser features come from src/legacy_browser.js.
    target: "chrome83",
  },
  optimizeDeps: {
    // Vite's dev pre-bundling rewrites neuroglancer's `new Worker(new URL(...))`
    // and breaks it. Dev only; the production build is unaffected.
    exclude: ["neuroglancer"],
  },
  server: {
    // Under `vite dev`, forward the data and the scene to the Python server.
    proxy: {
      "/data": "http://127.0.0.1:8848",
      "/api": "http://127.0.0.1:8848",
    },
  },
});
