/**
 * Workspace Monitor — Theme Provider
 *
 * Simplified light-only theme provider (Duolingo-style — always light).
 * Wraps MUI ThemeProvider + CssBaseline for global styling.
 *
 * Dependencies: react, @mui/material, ../theme.js
 */

import { ThemeProvider as MuiThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import theme from "../theme";

/**
 * ThemeProvider wraps the application with the Duolingo-inspired MUI theme.
 * Light-only — no dark mode toggle (consistent with Duolingo's approach).
 */
export function ThemeContextProvider({ children }) {
  return (
    <MuiThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </MuiThemeProvider>
  );
}

export default ThemeContextProvider;
