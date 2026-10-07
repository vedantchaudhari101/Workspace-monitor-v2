/**
 * Workspace Monitor — application entry point.
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "./styles/global.css";
import "./styles/components.css";
import { ThemeContextProvider } from "./context/ThemeContext";
import App from "./App";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ThemeContextProvider>
      <App />
    </ThemeContextProvider>
  </StrictMode>
);
