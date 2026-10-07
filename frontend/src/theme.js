/**
 * MUI theme mapped onto the design tokens in styles/tokens.css.
 *
 * Most of the interface is built from the product's own components; MUI is
 * kept for accessible primitives (Drawer, Tooltip, Snackbar) and is styled
 * here so those primitives match the rest of the UI.
 */

import { createTheme } from "@mui/material/styles";

export const tokens = {
  bg: "#0e1013",
  surface: "#14171b",
  surface2: "#1a1e23",
  surface3: "#22272d",
  line: "rgba(214, 226, 236, 0.08)",
  lineStrong: "rgba(214, 226, 236, 0.16)",
  text: "#e8ecef",
  text2: "#9aa3ad",
  text3: "#6a737d",
  scan: "#7fdbf0",
  occupied: "#ff5a5f",
  available: "#2ed47a",
  unknown: "#5b636c",
  warn: "#f2b84b",
  fontSans: '"Geist Variable", "Geist", ui-sans-serif, system-ui, sans-serif',
  fontMono: '"Geist Mono Variable", "Geist Mono", ui-monospace, monospace',
};

const theme = createTheme({
  palette: {
    mode: "dark",
    background: { default: tokens.bg, paper: tokens.surface },
    text: { primary: tokens.text, secondary: tokens.text2 },
    primary: { main: tokens.scan },
    error: { main: tokens.occupied },
    success: { main: tokens.available },
    warning: { main: tokens.warn },
    divider: tokens.line,
  },
  typography: {
    fontFamily: tokens.fontSans,
    button: { textTransform: "none", fontWeight: 500 },
  },
  shape: { borderRadius: 8 },
  components: {
    MuiCssBaseline: { styleOverrides: { body: { backgroundColor: tokens.bg } } },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: tokens.surface,
          backgroundImage: "none",
          borderLeft: `1px solid ${tokens.line}`,
        },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          backgroundColor: tokens.surface3,
          color: tokens.text,
          border: `1px solid ${tokens.lineStrong}`,
          fontSize: 12,
          padding: "8px 10px",
          borderRadius: 6,
        },
      },
    },
    MuiSnackbarContent: {
      styleOverrides: {
        root: {
          backgroundColor: tokens.surface3,
          color: tokens.text,
          border: `1px solid ${tokens.lineStrong}`,
        },
      },
    },
  },
});

export default theme;
