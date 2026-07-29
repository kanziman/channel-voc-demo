import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// Canonical design tokens (repo root — single source of truth, see ../DESIGN.md).
// Imported first so every component below can reference var(--token).
import "../../tokens.css";
import "./index.css";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
