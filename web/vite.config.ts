import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Design tokens live at the repo root (../tokens.css) as the single source of
// truth (see ../DESIGN.md). Allow Vite's dev server to read one level up so the
// frontend imports that canonical file instead of a drifting copy.
export default defineConfig({
  plugins: [react()],
  server: {
    fs: { allow: [".."] },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
