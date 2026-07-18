import { useState } from "react";
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Checkbox,
  FormControlLabel,
  InputAdornment,
  CircularProgress,
  IconButton,
  Link,
} from "@mui/material";
import EmailRoundedIcon from "@mui/icons-material/EmailRounded";
import LockRoundedIcon from "@mui/icons-material/LockRounded";
import Visibility from "@mui/icons-material/Visibility";
import VisibilityOff from "@mui/icons-material/VisibilityOff";
import AssessmentRoundedIcon from "@mui/icons-material/AssessmentRounded";

import { login, setAuthToken, getCurrentUser } from "../api/client";
import { duoColors } from "../theme";

export default function Login({ onLoginSuccess }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [emailError, setEmailError] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [loading, setLoading] = useState(false);

  const validateForm = () => {
    let isValid = true;
    setEmailError("");
    setPasswordError("");

    // Validate email
    if (!email) {
      setEmailError("Email address is required.");
      isValid = false;
    } else {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email)) {
        setEmailError("Please enter a valid email address.");
        isValid = false;
      }
    }

    // Validate password
    if (!password) {
      setPasswordError("Password is required.");
      isValid = false;
    }

    return isValid;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) return;

    setError("");
    setLoading(true);

    try {
      // 1. Authenticate with backend
      const res = await login(email, password);
      
      // 2. Save token using our rememberMe choice
      setAuthToken(res.access_token, rememberMe);

      // 3. Fetch user profile
      const user = await getCurrentUser();

      // 4. Trigger success callback
      onLoginSuccess(user);
    } catch (err) {
      console.error("Login failed:", err);
      setError(
        err.message || 
        "Invalid email or password. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  const togglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        bgcolor: duoColors.polar,
        p: 3,
      }}
    >
      <Card
        sx={{
          width: "100%",
          maxWidth: 420,
          borderRadius: "16px",
          border: `2px solid ${duoColors.swan}`,
          boxShadow: "0px 4px 20px rgba(0, 0, 0, 0.04)",
          p: 3,
        }}
      >
        <CardContent sx={{ p: 0 }}>
          {/* Logo & Product Heading */}
          <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", mb: 4 }}>
            <Box
              sx={{
                width: 56,
                height: 56,
                borderRadius: "12px",
                bgcolor: "#E3F2FD",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: duoColors.dodgerBlue,
                mb: 2,
              }}
            >
              <AssessmentRoundedIcon sx={{ fontSize: 32 }} />
            </Box>
            <Typography
              variant="h6"
              sx={{
                fontWeight: 800,
                fontSize: "1.25rem",
                color: duoColors.eel,
                fontFamily: "Nunito, sans-serif",
                textAlign: "center",
                mb: 0.5,
              }}
            >
              Workspace Occupancy Analytics Platform
            </Typography>
            <Typography
              variant="body2"
              sx={{
                fontWeight: 600,
                color: duoColors.wolf,
                fontFamily: "Nunito, sans-serif",
                textAlign: "center",
              }}
            >
              AI-powered Smart Workspace Monitoring
            </Typography>
          </Box>

          {/* Form Error Display */}
          {error && (
            <Box
              sx={{
                bgcolor: "#FFDFDF",
                border: `2px solid ${duoColors.cardinal}`,
                borderRadius: "10px",
                p: 1.5,
                mb: 3,
              }}
            >
              <Typography
                sx={{
                  color: duoColors.cardinal,
                  fontSize: "0.85rem",
                  fontWeight: 700,
                  fontFamily: "Nunito, sans-serif",
                }}
              >
                {error}
              </Typography>
            </Box>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit}>
            <Box sx={{ display: "flex", flexDirection: "column", gap: 2.5 }}>
              <TextField
                label="Email Address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                error={!!emailError}
                helperText={emailError}
                variant="outlined"
                fullWidth
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <EmailRoundedIcon sx={{ color: duoColors.wolf, fontSize: 20 }} />
                    </InputAdornment>
                  ),
                  sx: {
                    borderRadius: "10px",
                    fontFamily: "Nunito, sans-serif",
                    fontWeight: 600,
                  },
                }}
                InputLabelProps={{
                  sx: { fontFamily: "Nunito, sans-serif", fontWeight: 700 },
                }}
              />

              <TextField
                label="Password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                error={!!passwordError}
                helperText={passwordError}
                variant="outlined"
                fullWidth
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <LockRoundedIcon sx={{ color: duoColors.wolf, fontSize: 20 }} />
                    </InputAdornment>
                  ),
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton onClick={togglePasswordVisibility} edge="end">
                        {showPassword ? <VisibilityOff sx={{ fontSize: 20 }} /> : <Visibility sx={{ fontSize: 20 }} />}
                      </IconButton>
                    </InputAdornment>
                  ),
                  sx: {
                    borderRadius: "10px",
                    fontFamily: "Nunito, sans-serif",
                    fontWeight: 600,
                  },
                }}
                InputLabelProps={{
                  sx: { fontFamily: "Nunito, sans-serif", fontWeight: 700 },
                }}
              />

              {/* Remember Me and Forgot Password row */}
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={rememberMe}
                      onChange={(e) => setRememberMe(e.target.checked)}
                      color="primary"
                      sx={{
                        color: duoColors.swan,
                        "&.Mui-checked": {
                          color: duoColors.dodgerBlue,
                        },
                      }}
                    />
                  }
                  label={
                    <Typography sx={{ fontFamily: "Nunito, sans-serif", fontSize: "0.85rem", fontWeight: 700, color: duoColors.eel }}>
                      Remember Me
                    </Typography>
                  }
                />
                <Link
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    alert("Please contact system administrator to reset password.");
                  }}
                  sx={{
                    fontFamily: "Nunito, sans-serif",
                    fontSize: "0.85rem",
                    fontWeight: 700,
                    color: duoColors.dodgerBlue,
                    textDecoration: "none",
                    "&:hover": { textDecoration: "underline" },
                  }}
                >
                  Forgot Password?
                </Link>
              </Box>

              {/* Login Button */}
              <Button
                type="submit"
                disabled={loading}
                variant="contained"
                fullWidth
                sx={{
                  bgcolor: duoColors.dodgerBlue,
                  "&:hover": {
                    bgcolor: duoColors.dodgerBlueDark,
                  },
                  borderRadius: "10px",
                  py: 1.5,
                  fontFamily: "Nunito, sans-serif",
                  fontWeight: 800,
                  fontSize: "0.95rem",
                  boxShadow: "none",
                  textTransform: "none",
                }}
              >
                {loading ? <CircularProgress size={24} sx={{ color: "#FFF" }} /> : "Sign In"}
              </Button>
            </Box>
          </form>
        </CardContent>
      </Card>

      {/* Footer Branding */}
      <Typography
        variant="caption"
        sx={{
          mt: 3,
          fontFamily: "Nunito, sans-serif",
          fontWeight: 700,
          color: duoColors.wolf,
          fontSize: "0.75rem",
        }}
      >
        Powered by AI Computer Vision
      </Typography>
    </Box>
  );
}
