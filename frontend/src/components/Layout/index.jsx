/**
 * Workspace Monitor — Application Layout Shell (Duolingo Style)
 *
 * Clean, bright sidebar with rounded active states, friendly iconography,
 * and Duolingo's signature 3D border depth effects.
 *
 * Design Language:
 * - White sidebar with green accent for active items
 * - Bold, rounded typography
 * - No glassmorphism — clean solid surfaces
 * - Bright accent colors for each nav section
 * - Friendly, approachable feel
 *
 * Dependencies: react, react-router-dom, @mui/material, @mui/icons-material
 */

import { useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import {
  Box,
  Drawer,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
  Tooltip,
  Avatar,
  useMediaQuery,
  useTheme,
  Badge,
  Chip,
  Menu,
  MenuItem,
} from "@mui/material";

// Icons
import DashboardRoundedIcon from "@mui/icons-material/DashboardRounded";
import AnalyticsRoundedIcon from "@mui/icons-material/AnalyticsRounded";
import RecommendRoundedIcon from "@mui/icons-material/RecommendRounded";
import MenuRoundedIcon from "@mui/icons-material/MenuRounded";
import ChevronLeftRoundedIcon from "@mui/icons-material/ChevronLeftRounded";
import NotificationsRoundedIcon from "@mui/icons-material/NotificationsRounded";
import BusinessRoundedIcon from "@mui/icons-material/BusinessRounded";
import HelpOutlineRoundedIcon from "@mui/icons-material/HelpOutlineRounded";

import { duoColors } from "../../theme";

// ─── Constants ───────────────────────────────────────────────────────────────

const DRAWER_WIDTH_EXPANDED = 264;
const DRAWER_WIDTH_COLLAPSED = 76;

/**
 * Navigation items — each with a Duolingo-style accent color.
 * Disabled items show a "Coming" badge.
 */
const NAV_ITEMS = [
  {
    id: "dashboard",
    label: "Dashboard",
    icon: <DashboardRoundedIcon />,
    path: "/",
    color: duoColors.featherGreen,
  },
  {
    id: "analytics",
    label: "Analytics",
    icon: <AnalyticsRoundedIcon />,
    path: "/analytics",
    color: duoColors.beetle,
  },
  {
    id: "recommendations",
    label: "Recommendations",
    icon: <RecommendRoundedIcon />,
    path: "/recommendations",
    color: duoColors.beetle,
  },
];

// ─── Layout Component ────────────────────────────────────────────────────────

export default function Layout() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));
  const navigate = useNavigate();
  const location = useLocation();

  const [drawerOpen, setDrawerOpen] = useState(!isMobile);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [anchorEl, setAnchorEl] = useState(null);
  const menuOpen = Boolean(anchorEl);

  const userName = localStorage.getItem("user_name") || "Admin";
  const userEmail = localStorage.getItem("user_email") || "admin@workspace.com";
  const userInitial = userName.charAt(0).toUpperCase();

  const handleMenuClick = (event) => {
    setAnchorEl(event.currentTarget);
  };
  const handleMenuClose = () => {
    setAnchorEl(null);
  };
  const handleLogout = () => {
    localStorage.removeItem("workspace_monitor_token");
    localStorage.removeItem("user_name");
    localStorage.removeItem("user_email");
    window.location.reload();
  };

  const drawerWidth = drawerOpen ? DRAWER_WIDTH_EXPANDED : DRAWER_WIDTH_COLLAPSED;

  // ─── Nav Item Renderer ────────────────────────────────────────────

  const renderNavItem = (item) => {
    const isActive = location.pathname === item.path;

    return (
      <Tooltip
        key={item.id}
        title={!drawerOpen ? item.label : ""}
        placement="right"
        arrow
      >
        <ListItem disablePadding sx={{ mb: 0.5, px: 1 }}>
          <ListItemButton
            onClick={() => !item.disabled && navigate(item.path)}
            disabled={item.disabled}
            sx={{
              borderRadius: 3,
              minHeight: 48,
              justifyContent: drawerOpen ? "flex-start" : "center",
              px: drawerOpen ? 2 : 1.5,
              transition: "all 0.15s ease",
              border: "2px solid transparent",
              // Duolingo active state: colored background + bold
              ...(isActive && {
                bgcolor: `${item.color}18`,
                border: `2px solid ${item.color}40`,
                borderBottom: `3px solid ${item.color}60`,
                color: item.color,
              }),
              "&:hover": {
                bgcolor: isActive ? `${item.color}22` : duoColors.polar,
              },
              "&:active": {
                transform: "scale(0.98)",
              },
            }}
          >
            <ListItemIcon
              sx={{
                minWidth: drawerOpen ? 40 : 0,
                color: isActive ? item.color : duoColors.hare,
                transition: "color 0.15s ease",
              }}
            >
              {item.icon}
            </ListItemIcon>
            {drawerOpen && (
              <ListItemText
                primary={item.label}
                primaryTypographyProps={{
                  fontSize: "0.9rem",
                  fontWeight: isActive ? 800 : 600,
                  color: isActive ? item.color : duoColors.eel,
                }}
              />
            )}
            {drawerOpen && item.disabled && (
              <Chip
                label="SOON"
                size="small"
                sx={{
                  height: 22,
                  fontSize: "0.6rem",
                  fontWeight: 800,
                  letterSpacing: "0.05em",
                  bgcolor: duoColors.polar,
                  color: duoColors.hare,
                  border: `2px solid ${duoColors.swan}`,
                }}
              />
            )}
          </ListItemButton>
        </ListItem>
      </Tooltip>
    );
  };

  // ─── Sidebar Content ────────────────────────────────────────────────

  const sidebarContent = (
    <Box
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        bgcolor: duoColors.snow,
      }}
    >
      {/* Logo / Brand */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: drawerOpen ? "space-between" : "center",
          px: drawerOpen ? 2.5 : 1,
          py: 2,
          minHeight: 68,
        }}
      >
        {drawerOpen ? (
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <Box
              sx={{
                width: 38,
                height: 38,
                borderRadius: 3,
                bgcolor: duoColors.featherGreen,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                border: `2px solid ${duoColors.featherGreenDark}`,
                borderBottom: `4px solid ${duoColors.featherGreenDark}`,
              }}
            >
              <BusinessRoundedIcon sx={{ color: "#FFF", fontSize: 22 }} />
            </Box>
            <Box>
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 900,
                  fontSize: "1.1rem",
                  color: duoColors.eel,
                  lineHeight: 1.1,
                }}
              >
                WorkSpace
              </Typography>
              <Typography
                sx={{
                  fontSize: "0.65rem",
                  fontWeight: 700,
                  color: duoColors.featherGreen,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                }}
              >
                Monitor
              </Typography>
            </Box>
          </Box>
        ) : (
          <Box
            sx={{
              width: 38,
              height: 38,
              borderRadius: 3,
              bgcolor: duoColors.featherGreen,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              border: `2px solid ${duoColors.featherGreenDark}`,
              borderBottom: `4px solid ${duoColors.featherGreenDark}`,
            }}
          >
            <BusinessRoundedIcon sx={{ color: "#FFF", fontSize: 22 }} />
          </Box>
        )}
        {drawerOpen && (
          <IconButton
            onClick={() => (isMobile ? setMobileOpen(false) : setDrawerOpen(!drawerOpen))}
            size="small"
            sx={{
              border: `2px solid ${duoColors.swan}`,
              borderRadius: 2.5,
              width: 32,
              height: 32,
            }}
          >
            <ChevronLeftRoundedIcon sx={{ fontSize: 18 }} />
          </IconButton>
        )}
      </Box>

      <Divider sx={{ mx: 2, borderColor: duoColors.swan }} />

      {/* Main Navigation */}
      <List sx={{ flex: 1, py: 1.5 }}>{NAV_ITEMS.map(renderNavItem)}</List>

      {/* Help Card (Duolingo-style) */}
      {drawerOpen && (
        <Box sx={{ px: 2, pb: 2 }}>
          <Box
            sx={{
              p: 2,
              borderRadius: 4,
              bgcolor: "#E6F9D4",
              border: `2px solid ${duoColors.featherGreen}`,
              borderBottom: `4px solid ${duoColors.featherGreen}`,
              textAlign: "center",
            }}
          >
            <HelpOutlineRoundedIcon
              sx={{ color: duoColors.featherGreen, fontSize: 28, mb: 0.5 }}
            />
            <Typography
              sx={{
                fontSize: "0.8rem",
                fontWeight: 700,
                color: duoColors.featherGreenDark,
              }}
            >
              Need help?
            </Typography>
            <Typography
              sx={{
                fontSize: "0.7rem",
                fontWeight: 500,
                color: duoColors.featherGreenDark,
                opacity: 0.7,
              }}
            >
              Check the docs
            </Typography>
          </Box>
        </Box>
      )}
    </Box>
  );

  // ─── Render ──────────────────────────────────────────────────────────

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: duoColors.polar }}>
      {/* Sidebar */}
      {isMobile ? (
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          ModalProps={{ keepMounted: true }}
          sx={{
            "& .MuiDrawer-paper": {
              width: DRAWER_WIDTH_EXPANDED,
              boxSizing: "border-box",
            },
          }}
        >
          {sidebarContent}
        </Drawer>
      ) : (
        <Drawer
          variant="permanent"
          sx={{
            width: drawerWidth,
            flexShrink: 0,
            "& .MuiDrawer-paper": {
              width: drawerWidth,
              boxSizing: "border-box",
              transition: theme.transitions.create("width", {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
              }),
              overflowX: "hidden",
            },
          }}
        >
          {sidebarContent}
        </Drawer>
      )}

      {/* Main Content Area */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
        }}
      >
        {/* Top App Bar */}
        <AppBar position="sticky">
          <Toolbar sx={{ gap: 1 }}>
            {isMobile && (
              <IconButton onClick={() => setMobileOpen(true)} edge="start">
                <MenuRoundedIcon />
              </IconButton>
            )}
            {!isMobile && !drawerOpen && (
              <IconButton
                onClick={() => setDrawerOpen(true)}
                sx={{
                  border: `2px solid ${duoColors.swan}`,
                  borderRadius: 2.5,
                  width: 36,
                  height: 36,
                  mr: 1,
                }}
              >
                <MenuRoundedIcon sx={{ fontSize: 20 }} />
              </IconButton>
            )}

            <Typography
              variant="h5"
              sx={{
                flexGrow: 1,
                fontWeight: 800,
                fontSize: "1.15rem",
                color: duoColors.eel,
              }}
            >
              {NAV_ITEMS.find((i) => i.path === location.pathname)?.label ||
                "Workspace Monitor"}
            </Typography>

            {/* Notifications */}
            <Tooltip title="Notifications">
              <IconButton
                sx={{
                  border: `2px solid ${duoColors.swan}`,
                  borderRadius: 2.5,
                  width: 40,
                  height: 40,
                }}
              >
                <Badge
                  badgeContent={3}
                  sx={{
                    "& .MuiBadge-badge": {
                      bgcolor: duoColors.cardinal,
                      color: "#FFF",
                      fontWeight: 800,
                      fontSize: "0.65rem",
                      minWidth: 18,
                      height: 18,
                      border: `2px solid ${duoColors.snow}`,
                    },
                  }}
                >
                  <NotificationsRoundedIcon sx={{ fontSize: 20, color: duoColors.wolf }} />
                </Badge>
              </IconButton>
            </Tooltip>

            {/* User Avatar */}
            <Box
              onClick={handleMenuClick}
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 1,
                ml: 0.5,
                p: 0.5,
                pl: 1.5,
                borderRadius: 3,
                border: `2px solid ${duoColors.swan}`,
                cursor: "pointer",
                transition: "all 0.15s ease",
                "&:hover": { bgcolor: duoColors.polar },
              }}
            >
              <Typography
                sx={{
                  fontSize: "0.85rem",
                  fontWeight: 700,
                  color: duoColors.eel,
                  display: { xs: "none", sm: "block" },
                }}
              >
                {userName}
              </Typography>
              <Avatar
                sx={{
                  width: 32,
                  height: 32,
                  bgcolor: duoColors.featherGreen,
                  fontSize: "0.8rem",
                  fontWeight: 800,
                  border: `2px solid ${duoColors.featherGreenDark}`,
                }}
              >
                {userInitial}
              </Avatar>
            </Box>

            {/* Profile Dropdown Menu */}
            <Menu
              anchorEl={anchorEl}
              open={menuOpen}
              onClose={handleMenuClose}
              onClick={handleMenuClose}
              transformOrigin={{ horizontal: "right", vertical: "top" }}
              anchorOrigin={{ horizontal: "right", vertical: "bottom" }}
              PaperProps={{
                sx: {
                  mt: 1.5,
                  overflow: "visible",
                  borderRadius: "16px",
                  border: `2px solid ${duoColors.swan}`,
                  boxShadow: "0px 4px 12px rgba(0,0,0,0.08)",
                  "& .MuiAvatar-root": {
                    width: 32,
                    height: 32,
                    ml: -0.5,
                    mr: 1,
                  },
                },
              }}
            >
              <Box sx={{ px: 2, py: 1, minWidth: 160 }}>
                <Typography sx={{ fontWeight: 800, fontSize: "0.9rem", color: duoColors.eel }}>
                  {userName}
                </Typography>
                <Typography sx={{ fontSize: "0.75rem", color: duoColors.wolf }}>
                  {userEmail}
                </Typography>
              </Box>
              <Divider sx={{ my: 1, borderColor: duoColors.swan }} />
              <MenuItem
                onClick={handleLogout}
                sx={{
                  fontSize: "0.85rem",
                  fontWeight: 700,
                  color: duoColors.cardinal,
                  "&:hover": { bgcolor: "#FFDFDF" },
                }}
              >
                Log Out
              </MenuItem>
            </Menu>
          </Toolbar>
        </AppBar>

        {/* Page Content */}
        <Box
          sx={{
            flexGrow: 1,
            p: { xs: 2, sm: 3 },
            overflow: "auto",
          }}
        >
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
}
