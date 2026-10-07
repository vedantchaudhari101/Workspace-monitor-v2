/**
 * Theme provider — dark only for now (a light theme is planned separately).
 */

import { ThemeProvider as MuiThemeProvider } from "@mui/material/styles";
import theme from "../theme";

export function ThemeContextProvider({ children }) {
  return <MuiThemeProvider theme={theme}>{children}</MuiThemeProvider>;
}

export default ThemeContextProvider;
