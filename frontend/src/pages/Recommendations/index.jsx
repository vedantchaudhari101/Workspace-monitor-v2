import { useState, useEffect } from "react";
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Button,
  Chip,
  CircularProgress,
  Alert,
  Snackbar,
  Avatar,
  Divider,
} from "@mui/material";
import AutoAwesomeRoundedIcon from "@mui/icons-material/AutoAwesomeRounded";
import MonetizationOnRoundedIcon from "@mui/icons-material/MonetizationOnRounded";
import AirlineSeatReclineNormalRoundedIcon from "@mui/icons-material/AirlineSeatReclineNormalRounded";
import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";

import apiClient from "../../api/client";
import { duoColors } from "../../theme";

export default function Recommendations() {
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [alert, setAlert] = useState({ open: false, message: "", severity: "success" });
  const [actionInProgress, setActionInProgress] = useState({});

  const fetchRecommendations = async () => {
    setLoading(true);
    try {
      const data = await apiClient.get("/recommendations");
      // Filter to only display PENDING recommendations
      const pending = (data.items || []).filter((r) => r.status === "PENDING" || r.status === "pending");
      setRecommendations(pending);
    } catch (err) {
      setError("Failed to fetch seat recommendations");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecommendations();
  }, []);

  const handleAction = async (id, action) => {
    setActionInProgress((prev) => ({ ...prev, [id]: true }));
    try {
      if (action === "approve") {
        await apiClient.post(`/recommendations/${id}/approve`);
        setAlert({
          open: true,
          message: "Recommendation approved and allocations updated successfully!",
          severity: "success",
        });
      } else {
        await apiClient.post(`/recommendations/${id}/reject`);
        setAlert({
          open: true,
          message: "Recommendation rejected and archived.",
          severity: "warning",
        });
      }
      // Reload list
      await fetchRecommendations();
    } catch (err) {
      setAlert({
        open: true,
        message: err.message || "Failed to process recommendation action.",
        severity: "error",
      });
    } finally {
      setActionInProgress((prev) => ({ ...prev, [id]: false }));
    }
  };

  // Helper for priority badges
  const getPriorityStyle = (priority) => {
    const p = String(priority).toUpperCase();
    if (p === "CRITICAL") return { bg: "#FFE0E0", border: duoColors.cardinal, text: duoColors.cardinalDark };
    if (p === "HIGH") return { bg: "#FFF4CC", border: duoColors.fox, text: duoColors.foxDark };
    if (p === "MEDIUM") return { bg: "#DDF2FE", border: duoColors.dodgerBlue, text: duoColors.dodgerBlueDark };
    return { bg: "#E6F9D4", border: duoColors.featherGreen, text: duoColors.featherGreenDark };
  };

  return (
    <Box>
      {/* Title */}
      <Box sx={{ mb: 4, display: "flex", alignItems: "center", gap: 2 }}>
        <Avatar sx={{ bgcolor: "#CE82FF", width: 56, height: 56, border: "2px solid #B666E5", borderBottom: "5px solid #B666E5" }}>
          <AutoAwesomeRoundedIcon sx={{ color: "#FFF", fontSize: 30 }} />
        </Avatar>
        <Box>
          <Typography variant="h3" sx={{ fontWeight: 900, color: duoColors.eel }}>
            AI Seating Recommendations
          </Typography>
          <Typography variant="body1" sx={{ color: duoColors.wolf }}>
            Optimize spatial density and reduce unused seat expenditures
          </Typography>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3, borderRadius: 3 }}>
          {error}
        </Alert>
      )}

      {/* Main List */}
      {loading ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
          <CircularProgress color="primary" />
        </Box>
      ) : recommendations.length === 0 ? (
        <Card sx={{ p: 6, textAlign: "center", borderStyle: "dashed" }}>
          <Typography variant="h5" sx={{ fontWeight: 900, color: duoColors.wolf, mb: 1 }}>
            🎉 Workspace Fully Optimized!
          </Typography>
          <Typography variant="body2" sx={{ color: duoColors.hare }}>
            No new pending recommendations. All tenant startups are utilizing their seats efficiently.
          </Typography>
        </Card>
      ) : (
        <Grid container spacing={3}>
          {recommendations.map((rec) => {
            const pStyle = getPriorityStyle(rec.priority);
            return (
              <Grid item xs={12} key={rec.id}>
                <Card
                  sx={{
                    borderColor: duoColors.swan,
                    borderBottomColor: duoColors.swan,
                    overflow: "visible",
                    position: "relative",
                  }}
                >
                  <CardContent sx={{ p: 3 }}>
                    <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 2, flexWrap: "wrap", gap: 2 }}>
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                        <Chip
                          label={String(rec.priority).toUpperCase()}
                          sx={{
                            bgcolor: pStyle.bg,
                            border: `2px solid ${pStyle.border}`,
                            color: pStyle.text,
                            fontWeight: 800,
                            height: 26,
                          }}
                        />
                        <Chip
                          label={String(rec.recommendation_type).toUpperCase()}
                          sx={{
                            bgcolor: "#FFFFFF",
                            border: `2px solid ${duoColors.swan}`,
                            color: duoColors.eel,
                            fontWeight: 800,
                            height: 26,
                          }}
                        />
                      </Box>
                      
                      {/* Impact metrics */}
                      <Box sx={{ display: "flex", gap: 1.5 }}>
                        {rec.impact_revenue > 0 && (
                          <Box
                            sx={{
                              display: "flex",
                              alignItems: "center",
                              gap: 0.5,
                              px: 1.5,
                              py: 0.5,
                              borderRadius: 2.5,
                              bgcolor: "#E6F9D4",
                              border: `2px solid ${duoColors.featherGreen}`,
                            }}
                          >
                            <MonetizationOnRoundedIcon sx={{ fontSize: 16, color: duoColors.featherGreenDark }} />
                            <Typography sx={{ fontWeight: 800, fontSize: "0.75rem", color: duoColors.featherGreenDark }}>
                              Saves ${rec.impact_revenue.toLocaleString()}/mo
                            </Typography>
                          </Box>
                        )}
                        {rec.impact_seats > 0 && (
                          <Box
                            sx={{
                              display: "flex",
                              alignItems: "center",
                              gap: 0.5,
                              px: 1.5,
                              py: 0.5,
                              borderRadius: 2.5,
                              bgcolor: "#DDF2FE",
                              border: `2px solid ${duoColors.dodgerBlue}`,
                            }}
                          >
                            <AirlineSeatReclineNormalRoundedIcon sx={{ fontSize: 16, color: duoColors.dodgerBlueDark }} />
                            <Typography sx={{ fontWeight: 800, fontSize: "0.75rem", color: duoColors.dodgerBlueDark }}>
                              Frees {rec.impact_seats} seats
                            </Typography>
                          </Box>
                        )}
                      </Box>
                    </Box>

                    {/* Recommendation Content */}
                    <Typography variant="h5" sx={{ fontWeight: 900, mb: 1.5 }}>
                      {rec.title}
                    </Typography>
                    <Typography variant="body1" sx={{ color: duoColors.wolf, mb: 3 }}>
                      {rec.description}
                    </Typography>

                    <Divider sx={{ my: 2, borderColor: duoColors.swan }} />

                    {/* Action buttons */}
                    <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 2 }}>
                      <Button
                        variant="outlined"
                        onClick={() => handleAction(rec.id, "reject")}
                        disabled={actionInProgress[rec.id]}
                        sx={{
                          borderColor: duoColors.swan,
                          "&:hover": {
                            borderColor: duoColors.cardinal,
                            backgroundColor: "#FFE0E0",
                          },
                        }}
                      >
                        Reject
                      </Button>
                      <Button
                        variant="contained"
                        onClick={() => handleAction(rec.id, "approve")}
                        disabled={actionInProgress[rec.id]}
                        endIcon={actionInProgress[rec.id] ? <CircularProgress size={16} color="inherit" /> : <ArrowForwardRoundedIcon />}
                        sx={{
                          backgroundColor: duoColors.featherGreen,
                          "&:hover": {
                            backgroundColor: duoColors.featherGreenLight,
                          },
                        }}
                      >
                        Approve
                      </Button>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            );
          })}
        </Grid>
      )}

      {/* Snackbar feedback */}
      <Snackbar
        open={alert.open}
        autoHideDuration={5000}
        onClose={() => setAlert((prev) => ({ ...prev, open: false }))}
      >
        <Alert severity={alert.severity} variant="filled" sx={{ borderRadius: 3, fontWeight: 700 }}>
          {alert.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
