/**
 * Workspace Monitor — Application Entry Point
 *
 * Mounts the React application with all required providers:
 * - StrictMode for development warnings
 * - ThemeContextProvider for dark/light mode
 *
 * Dependencies: react, react-dom, ThemeContextProvider, App
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ThemeContextProvider } from "./context/ThemeContext";
import App from "./App";

// Import Inter font from Google Fonts (added to index.html as well)
import "./index.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ThemeContextProvider>
      <App />
    </ThemeContextProvider>
  </StrictMode>
);
