/**
 * Workspace Monitor — Material UI Theme Configuration
 *
 * Duolingo-inspired design system with a vibrant, clean, light-only aesthetic.
 * Uses Duolingo's official color palette adapted for a workspace monitoring context.
 *
 * Color Reference (from Duolingo Brand Guidelines):
 *   Feather Green:  #58CC02  — Primary actions, positive indicators
 *   Mask Green:     #89E219  — Secondary green, highlights
 *   Dodger Blue:    #1CB0F6  — Info, links, analytics
 *   Cardinal Red:   #FF4B4B  — Errors, revenue leakage, over-utilization
 *   Bee Yellow:     #FFC800  — Warnings, under-utilization alerts
 *   Fox Orange:     #FF9600  — Secondary warnings, peak indicators
 *   Beetle Purple:  #CE82FF  — Recommendations, insights
 *   Eel:            #4B4B4B  — Primary text
 *   Wolf:           #777777  — Secondary text
 *   Hare:           #AFAFAF  — Muted text, placeholders
 *   Swan:           #E5E5E5  — Borders, dividers
 *   Snow:           #FFFFFF  — Backgrounds
 *
 * Dependencies: @mui/material
 */

import { createTheme } from "@mui/material/styles";

// ─── Duolingo Color Palette ──────────────────────────────────────────────────
const duoColors = {
  featherGreen: "#58CC02",
  featherGreenDark: "#46A302",
  featherGreenLight: "#7CD627",
  maskGreen: "#89E219",
  dodgerBlue: "#1CB0F6",
  dodgerBlueDark: "#1899D6",
  cardinal: "#FF4B4B",
  cardinalDark: "#EA2B2B",
  bee: "#FFC800",
  beeDark: "#E5B800",
  fox: "#FF9600",
  foxDark: "#E88600",
  beetle: "#CE82FF",
  beetleDark: "#B666E5",
  eel: "#4B4B4B",
  wolf: "#777777",
  hare: "#AFAFAF",
  swan: "#E5E5E5",
  polar: "#F7F7F7",
  snow: "#FFFFFF",
};

// ─── Typography ──────────────────────────────────────────────────────────────
const typography = {
  fontFamily: '"Nunito", "DM Sans", "Roboto", "Helvetica Neue", Arial, sans-serif',
  h1: {
    fontWeight: 800,
    fontSize: "2.25rem",
    lineHeight: 1.2,
    letterSpacing: "-0.01em",
    color: duoColors.eel,
  },
  h2: {
    fontWeight: 800,
    fontSize: "1.875rem",
    lineHeight: 1.25,
    color: duoColors.eel,
  },
  h3: {
    fontWeight: 700,
    fontSize: "1.5rem",
    lineHeight: 1.3,
    color: duoColors.eel,
  },
  h4: {
    fontWeight: 700,
    fontSize: "1.25rem",
    lineHeight: 1.35,
    color: duoColors.eel,
  },
  h5: {
    fontWeight: 700,
    fontSize: "1.1rem",
    lineHeight: 1.4,
    color: duoColors.eel,
  },
  h6: {
    fontWeight: 700,
    fontSize: "1rem",
    lineHeight: 1.45,
    color: duoColors.eel,
  },
  subtitle1: {
    fontWeight: 600,
    fontSize: "0.95rem",
    lineHeight: 1.5,
  },
  subtitle2: {
    fontWeight: 600,
    fontSize: "0.85rem",
    lineHeight: 1.55,
  },
  body1: {
    fontWeight: 500,
    fontSize: "0.938rem",
    lineHeight: 1.6,
    color: duoColors.eel,
  },
  body2: {
    fontWeight: 500,
    fontSize: "0.85rem",
    lineHeight: 1.6,
    color: duoColors.wolf,
  },
  button: {
    fontWeight: 700,
    textTransform: "none",
    letterSpacing: "0.02em",
    fontSize: "0.938rem",
  },
  overline: {
    fontWeight: 700,
    fontSize: "0.7rem",
    letterSpacing: "0.1em",
    textTransform: "uppercase",
    color: duoColors.wolf,
  },
};

// ─── Component Overrides (Duolingo Style) ────────────────────────────────────
const components = {
  MuiCssBaseline: {
    styleOverrides: {
      body: {
        backgroundColor: duoColors.polar,
        scrollbarWidth: "thin",
        "&::-webkit-scrollbar": {
          width: "8px",
          height: "8px",
        },
        "&::-webkit-scrollbar-track": {
          background: duoColors.polar,
        },
        "&::-webkit-scrollbar-thumb": {
          background: duoColors.swan,
          borderRadius: "4px",
        },
        "&::-webkit-scrollbar-thumb:hover": {
          background: duoColors.hare,
        },
      },
    },
  },
  MuiButton: {
    defaultProps: {
      disableElevation: true,
      disableRipple: true,
    },
    styleOverrides: {
      root: {
        borderRadius: 14,
        padding: "10px 24px",
        fontSize: "0.938rem",
        fontWeight: 700,
        transition: "all 0.15s ease",
        position: "relative",
        "&:active": {
          transform: "translateY(2px)",
        },
      },
      contained: {
        // Duolingo's signature 3D button effect
        boxShadow: "none",
        "&:hover": {
          boxShadow: "none",
        },
      },
      containedPrimary: {
        backgroundColor: duoColors.featherGreen,
        borderBottom: `4px solid ${duoColors.featherGreenDark}`,
        color: "#FFFFFF",
        "&:hover": {
          backgroundColor: duoColors.featherGreenLight,
          borderBottomColor: duoColors.featherGreen,
        },
        "&:active": {
          borderBottom: "0px solid transparent",
          marginTop: "4px",
        },
      },
      containedSecondary: {
        backgroundColor: duoColors.dodgerBlue,
        borderBottom: `4px solid ${duoColors.dodgerBlueDark}`,
        color: "#FFFFFF",
        "&:hover": {
          backgroundColor: "#49BDF7",
          borderBottomColor: duoColors.dodgerBlue,
        },
        "&:active": {
          borderBottom: "0px solid transparent",
          marginTop: "4px",
        },
      },
      outlined: {
        borderWidth: 2,
        borderColor: duoColors.swan,
        borderBottom: `4px solid ${duoColors.swan}`,
        color: duoColors.eel,
        backgroundColor: duoColors.snow,
        "&:hover": {
          borderWidth: 2,
          backgroundColor: duoColors.polar,
          borderColor: duoColors.hare,
          borderBottomColor: duoColors.hare,
        },
        "&:active": {
          borderBottomWidth: 2,
          marginTop: "2px",
        },
      },
    },
  },
  MuiCard: {
    defaultProps: {
      elevation: 0,
    },
    styleOverrides: {
      root: {
        borderRadius: 16,
        border: `2px solid ${duoColors.swan}`,
        backgroundColor: duoColors.snow,
        transition: "all 0.15s ease",
        // Duolingo's signature bottom border depth
        borderBottom: `4px solid ${duoColors.swan}`,
        "&:hover": {
          borderColor: duoColors.hare,
          borderBottomColor: duoColors.hare,
        },
      },
    },
  },
  MuiPaper: {
    defaultProps: {
      elevation: 0,
    },
    styleOverrides: {
      root: {
        backgroundImage: "none",
        borderRadius: 16,
      },
    },
  },
  MuiAppBar: {
    defaultProps: {
      elevation: 0,
    },
    styleOverrides: {
      root: {
        backgroundColor: duoColors.snow,
        color: duoColors.eel,
        borderBottom: `2px solid ${duoColors.swan}`,
      },
    },
  },
  MuiDrawer: {
    styleOverrides: {
      paper: {
        border: "none",
        borderRight: `2px solid ${duoColors.swan}`,
        backgroundImage: "none",
        backgroundColor: duoColors.snow,
      },
    },
  },
  MuiChip: {
    styleOverrides: {
      root: {
        borderRadius: 10,
        fontWeight: 700,
        fontSize: "0.75rem",
        border: "2px solid transparent",
      },
      colorSuccess: {
        backgroundColor: "#E6F9D4",
        color: duoColors.featherGreenDark,
        border: `2px solid ${duoColors.featherGreen}`,
      },
      colorWarning: {
        backgroundColor: "#FFF4CC",
        color: duoColors.foxDark,
        border: `2px solid ${duoColors.bee}`,
      },
      colorError: {
        backgroundColor: "#FFE0E0",
        color: duoColors.cardinalDark,
        border: `2px solid ${duoColors.cardinal}`,
      },
      colorInfo: {
        backgroundColor: "#DDF2FE",
        color: duoColors.dodgerBlueDark,
        border: `2px solid ${duoColors.dodgerBlue}`,
      },
    },
  },
  MuiLinearProgress: {
    styleOverrides: {
      root: {
        borderRadius: 8,
        height: 12,
        backgroundColor: duoColors.swan,
      },
      bar: {
        borderRadius: 8,
      },
    },
  },
  MuiTooltip: {
    styleOverrides: {
      tooltip: {
        borderRadius: 10,
        fontSize: "0.8rem",
        fontWeight: 600,
        padding: "8px 14px",
        backgroundColor: duoColors.eel,
      },
    },
  },
  MuiAlert: {
    styleOverrides: {
      root: {
        borderRadius: 16,
        fontWeight: 600,
        border: "2px solid",
        borderBottom: "4px solid",
      },
      standardSuccess: {
        backgroundColor: "#E6F9D4",
        borderColor: duoColors.featherGreen,
        color: duoColors.featherGreenDark,
      },
      standardWarning: {
        backgroundColor: "#FFF4CC",
        borderColor: duoColors.bee,
        color: duoColors.foxDark,
      },
      standardError: {
        backgroundColor: "#FFE0E0",
        borderColor: duoColors.cardinal,
        color: duoColors.cardinalDark,
      },
      standardInfo: {
        backgroundColor: "#DDF2FE",
        borderColor: duoColors.dodgerBlue,
        color: duoColors.dodgerBlueDark,
      },
    },
  },
  MuiIconButton: {
    defaultProps: {
      disableRipple: true,
    },
    styleOverrides: {
      root: {
        borderRadius: 12,
        transition: "all 0.15s ease",
        "&:hover": {
          backgroundColor: duoColors.polar,
        },
      },
    },
  },
  MuiListItemButton: {
    defaultProps: {
      disableRipple: true,
    },
  },
};

// ─── Theme ───────────────────────────────────────────────────────────────────

const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: duoColors.featherGreen,
      light: duoColors.maskGreen,
      dark: duoColors.featherGreenDark,
      contrastText: "#FFFFFF",
    },
    secondary: {
      main: duoColors.dodgerBlue,
      light: "#49BDF7",
      dark: duoColors.dodgerBlueDark,
      contrastText: "#FFFFFF",
    },
    success: {
      main: duoColors.featherGreen,
      light: "#7CD627",
      dark: duoColors.featherGreenDark,
    },
    warning: {
      main: duoColors.fox,
      light: duoColors.bee,
      dark: duoColors.foxDark,
    },
    error: {
      main: duoColors.cardinal,
      light: "#FF7676",
      dark: duoColors.cardinalDark,
    },
    info: {
      main: duoColors.dodgerBlue,
      light: "#49BDF7",
      dark: duoColors.dodgerBlueDark,
    },
    background: {
      default: duoColors.polar,
      paper: duoColors.snow,
    },
    text: {
      primary: duoColors.eel,
      secondary: duoColors.wolf,
      disabled: duoColors.hare,
    },
    divider: duoColors.swan,
  },
  typography,
  shape: {
    borderRadius: 14,
  },
  components,
});

// Export color constants for direct use in custom components
export { duoColors };
export default theme;
