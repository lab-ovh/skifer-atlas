import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Port fixe : tauri.conf.json (devUrl) et la liste CORS du serveur Python en dépendent.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: { port: 1420, strictPort: true },
  envPrefix: ["VITE_", "TAURI_"],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      include: ["src/**"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/test/**"],
      reporter: ["text", "json-summary"],
      // Sous la couverture mesurée le 15 novembre 2026 (99,1 / 92,4 / 96,2 / 99,1) : une baisse nette bloque la PR (ADR 0062).
      thresholds: { lines: 98, statements: 98, functions: 95, branches: 91 },
    },
  },
});
