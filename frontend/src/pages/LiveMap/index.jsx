import { useState, useEffect, useRef } from "react";
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
  ButtonGroup,
  Tooltip,
  Alert,
  Snackbar,
  CircularProgress,
} from "@mui/material";
import VideocamRoundedIcon from "@mui/icons-material/VideocamRounded";
import UploadFileRoundedIcon from "@mui/icons-material/UploadFileRounded";
import PlayCircleRoundedIcon from "@mui/icons-material/PlayCircleRounded";
import ChairRoundedIcon from "@mui/icons-material/ChairRounded";
import WifiRoundedIcon from "@mui/icons-material/WifiRounded";
import WifiOffRoundedIcon from "@mui/icons-material/WifiOffRounded";

import apiClient, { setAuthToken } from "../../api/client";
import { duoColors } from "../../theme";

export default function LiveMap() {
  const [buildings, setBuildings] = useState([]);
  const [selectedBuilding, setSelectedBuilding] = useState("");
  const [selectedFloor, setSelectedFloor] = useState("");
  const [selectedZone, setSelectedZone] = useState("");
  
  const [buildingDetail, setBuildingDetail] = useState(null);
  const [seats, setSeats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [wsConnected, setWsConnected] = useState(false);
  const [cameraUpdating, setCameraUpdating] = useState(false);
  const [alert, setAlert] = useState({ open: false, message: "", severity: "info" });
  
  const wsRef = useRef(null);
  const fileInputRef = useRef(null);
  const [activeUploadCameraId, setActiveUploadCameraId] = useState(null);

  // Fetch all buildings on mount
  useEffect(() => {
    const fetchBuildings = async () => {
      const performAutoLogin = async () => {
        try {
          const loginResponse = await apiClient.post("/auth/login/json", {
            email: "admin@workspace.dev",
            password: "Admin@12345",
          });
          if (loginResponse.access_token) {
            setAuthToken(loginResponse.access_token);
            return true;
          }
        } catch (err) {
          console.error("Auto-login failed:", err);
        }
        return false;
      };

      const doFetch = async () => {
        const data = await apiClient.get("/buildings");
        setBuildings(data);
        if (data.length > 0) {
          setSelectedBuilding(data[0].id);
        }
      };

      try {
        let token = localStorage.getItem("workspace_monitor_token");
        if (!token) {
          await performAutoLogin();
        }
        try {
          await doFetch();
        } catch (err) {
          if (err?.response?.status === 401 || err?.status === 401) {
             const success = await performAutoLogin();
             if (success) {
               await doFetch();
             } else {
               throw err;
             }
          } else {
             throw err;
          }
        }
      } catch (err) {
        showFeedback("Failed to load buildings", "error");
      }
    };
    fetchBuildings();
  }, []);

  // Fetch building details and live occupancy when selected building changes
  useEffect(() => {
    if (!selectedBuilding) return;

    const fetchBuildingData = async () => {
      setLoading(true);
      try {
        const detail = await apiClient.get(`/buildings/${selectedBuilding}`);
        setBuildingDetail(detail);

        const liveData = await apiClient.get(`/occupancy/live/${selectedBuilding}`);
        setSeats(liveData.seats || []);

        // Pre-select first floor if available
        if (detail.floors && detail.floors.length > 0) {
          setSelectedFloor(detail.floors[0].id);
        } else {
          setSelectedFloor("");
        }
        setSelectedZone("");
      } catch (err) {
        showFeedback("Failed to fetch occupancy layout", "error");
      } finally {
        setLoading(false);
      }
    };

    fetchBuildingData();
  }, [selectedBuilding]);

  // Set up WebSocket connection for real-time seat occupancy updates
  useEffect(() => {
    const getWsUrl = () => {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = import.meta.env.VITE_API_BASE_URL
        ? import.meta.env.VITE_API_BASE_URL.replace(/^https?:\/\//, "")
        : window.location.host;
      return `${protocol}//${host}/api/v1/occupancy/ws`;
    };
    const wsUrl = getWsUrl();
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      showFeedback("Live occupancy stream connected", "success");
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "seat_update") {
          setSeats((prevSeats) =>
            prevSeats.map((seat) =>
              seat.seat_id === message.seat_id
                ? { ...seat, status: message.status }
                : seat
            )
          );
        }
      } catch (err) {
        console.error("Error parsing WebSocket message:", err);
      }
    };

    ws.onerror = (err) => {
      console.error("WebSocket error:", err);
      setWsConnected(false);
    };

    ws.onclose = () => {
      setWsConnected(false);
    };

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const showFeedback = (message, severity = "info") => {
    setAlert({ open: true, message, severity });
  };

  const handleCameraSourceChange = async (cameraId, sourceType) => {
    setCameraUpdating(true);
    try {
      await apiClient.post(`/occupancy/camera/${cameraId}/source`, {
        source_type: sourceType,
        video_path: sourceType === "video" ? "sample_feed.mp4" : null,
        webcam_index: sourceType === "webcam" ? 0 : null,
      });
      showFeedback(`Camera source changed to ${sourceType}`, "success");
      
      // Update local building detail config
      setBuildingDetail((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          cameras: prev.cameras.map((c) =>
            c.id === cameraId ? { ...c, stream_url: sourceType } : c
          ),
        };
      });
    } catch (err) {
      showFeedback("Failed to update camera source", "error");
    } finally {
      setCameraUpdating(false);
    }
  };

  const triggerVideoUpload = (cameraId) => {
    setActiveUploadCameraId(cameraId);
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleVideoUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    if (!activeUploadCameraId) {
      showFeedback("No camera selected for video upload.", "error");
      event.target.value = null;
      return;
    }

    setCameraUpdating(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await apiClient.post(
        `/occupancy/camera/${activeUploadCameraId}/upload-video`,
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        }
      );
      showFeedback("Video uploaded successfully. Occupancy processing started.", "success");
      
      setBuildingDetail((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          cameras: prev.cameras.map((c) =>
            c.id === activeUploadCameraId ? { ...c, stream_url: response.file_path } : c
          ),
        };
      });
    } catch (err) {
      showFeedback("Failed to upload video file", "error");
    } finally {
      setCameraUpdating(false);
      event.target.value = null; // Clear input
    }
  };

  // Filter seats based on current selections
  const filteredSeats = seats.filter((seat) => {
    const matchesFloor = !selectedFloor || seat.floor_id === selectedFloor;
    const matchesZone = !selectedZone || seat.zone_id === selectedZone;
    return matchesFloor && matchesZone;
  });

  // Extract unique zones for the selected floor from current seats
  const zonesForFloor = Array.from(
    new Map(
      seats
        .filter((seat) => !selectedFloor || seat.floor_id === selectedFloor)
        .map((seat) => [seat.zone_id, seat.zone_name])
    ).entries()
  ).map(([id, name]) => ({ id, name }));

  // Helper to determine Duolingo style seat styling and colors
  const getSeatColor = (status, seat) => {
    if (status === "OVER_UTILIZED" || (status === "OCCUPIED" && seat.startup_name === "Startup D")) {
      return {
        bg: "#FFE0E0",
        border: duoColors.cardinal,
        borderBottom: duoColors.cardinalDark,
        text: duoColors.cardinalDark,
      };
    }
    if (status === "OCCUPIED") {
      return {
        bg: "#E6F9D4",
        border: duoColors.featherGreen,
        borderBottom: duoColors.featherGreenDark,
        text: duoColors.featherGreenDark,
      };
    }
    return {
      bg: "#FFFFFF",
      border: duoColors.swan,
      borderBottom: "#C0C0C0",
      text: duoColors.wolf,
    };
  };

  // Compute metrics for current selections
  const totalCount = filteredSeats.length;
  const occupiedCount = filteredSeats.filter((s) => s.status === "OCCUPIED" && s.startup_name !== "Startup D").length;
  const overUtilizedCount = filteredSeats.filter((s) => s.status === "OVER_UTILIZED" || (s.status === "OCCUPIED" && s.startup_name === "Startup D")).length;
  const vacantCount = totalCount - occupiedCount - overUtilizedCount;

  return (
    <Box>
      {/* Page Title & Connection Status */}
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 3 }}>
        <Box>
          <Typography variant="h3" sx={{ fontWeight: 900, color: duoColors.eel }}>
            Live Seat Map
          </Typography>
          <Typography variant="body1" sx={{ color: duoColors.wolf }}>
            View and manage real-time seating layouts
          </Typography>
        </Box>
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1,
            px: 2,
            py: 0.8,
            borderRadius: 3,
            border: `2px solid ${wsConnected ? duoColors.featherGreen : duoColors.cardinal}`,
            backgroundColor: wsConnected ? "#E6F9D4" : "#FFE0E0",
          }}
        >
          {wsConnected ? (
            <>
              <WifiRoundedIcon sx={{ color: duoColors.featherGreenDark }} />
              <Typography sx={{ fontWeight: 800, fontSize: "0.85rem", color: duoColors.featherGreenDark }}>
                LIVE FEED ACTIVE
              </Typography>
            </>
          ) : (
            <>
              <WifiOffRoundedIcon sx={{ color: duoColors.cardinalDark }} />
              <Typography sx={{ fontWeight: 800, fontSize: "0.85rem", color: duoColors.cardinalDark }}>
                OFFLINE
              </Typography>
            </>
          )}
        </Box>
      </Box>

      {/* Selectors Bar */}
      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ p: 2.5 }}>
          <Grid container spacing={2} alignItems="center">
            {/* Building Selector */}
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth size="small">
                <InputLabel sx={{ fontFamily: "Nunito", fontWeight: 700 }}>Building</InputLabel>
                <Select
                  value={selectedBuilding}
                  label="Building"
                  onChange={(e) => setSelectedBuilding(e.target.value)}
                  sx={{ borderRadius: 3, fontWeight: 700, fontFamily: "Nunito" }}
                >
                  {buildings.map((b) => (
                    <MenuItem key={b.id} value={b.id} sx={{ fontFamily: "Nunito", fontWeight: 700 }}>
                      {b.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            {/* Floor Selector */}
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth size="small" disabled={loading || !buildingDetail}>
                <InputLabel sx={{ fontFamily: "Nunito", fontWeight: 700 }}>Floor</InputLabel>
                <Select
                  value={selectedFloor}
                  label="Floor"
                  onChange={(e) => {
                    setSelectedFloor(e.target.value);
                    setSelectedZone("");
                  }}
                  sx={{ borderRadius: 3, fontWeight: 700, fontFamily: "Nunito" }}
                >
                  <MenuItem value="" sx={{ fontFamily: "Nunito", fontWeight: 700 }}>All Floors</MenuItem>
                  {buildingDetail?.floors?.map((f) => (
                    <MenuItem key={f.id} value={f.id} sx={{ fontFamily: "Nunito", fontWeight: 700 }}>
                      {f.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            {/* Zone Selector */}
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth size="small" disabled={loading || !selectedFloor}>
                <InputLabel sx={{ fontFamily: "Nunito", fontWeight: 700 }}>Zone</InputLabel>
                <Select
                  value={selectedZone}
                  label="Zone"
                  onChange={(e) => setSelectedZone(e.target.value)}
                  sx={{ borderRadius: 3, fontWeight: 700, fontFamily: "Nunito" }}
                >
                  <MenuItem value="" sx={{ fontFamily: "Nunito", fontWeight: 700 }}>All Zones</MenuItem>
                  {zonesForFloor.map((z) => (
                    <MenuItem key={z.id} value={z.id} sx={{ fontFamily: "Nunito", fontWeight: 700 }}>
                      {z.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Camera Controls */}
      {buildingDetail?.cameras && buildingDetail.cameras.length > 0 && (
        <Card sx={{ mb: 3, p: 2 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 1.5 }}>
            <VideocamRoundedIcon sx={{ color: duoColors.dodgerBlue }} />
            <Typography variant="h6" sx={{ fontWeight: 800, fontFamily: "Nunito" }}>
              CCTV Camera Integration & Live Feeds
            </Typography>
          </Box>
          <Grid container spacing={2}>
            {buildingDetail.cameras
              .filter((c) => !selectedFloor || c.floor_id === selectedFloor)
              .map((camera) => (
                <Grid item xs={12} md={6} key={camera.id}>
                  <Box
                    sx={{
                      p: 2,
                      borderRadius: 4,
                      border: `2px solid ${duoColors.swan}`,
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      backgroundColor: "#F7F7F7",
                    }}
                  >
                    <Box>
                      <Typography sx={{ fontWeight: 800, fontSize: "0.9rem" }}>{camera.name}</Typography>
                      <Typography variant="caption" sx={{ color: duoColors.wolf }}>
                        Stream: {camera.stream_url}
                      </Typography>
                    </Box>
                    <ButtonGroup size="small" variant="outlined" disabled={cameraUpdating}>
                      <Tooltip title="Upload Video">
                        <Button
                          onClick={() => triggerVideoUpload(camera.id)}
                          sx={{
                            backgroundColor: camera.stream_url.includes("video") || camera.stream_url.includes("mp4") ? "#DDF2FE" : "transparent",
                            borderColor: duoColors.swan,
                          }}
                        >
                          <UploadFileRoundedIcon fontSize="small" />
                        </Button>
                      </Tooltip>
                      <Tooltip title="Mock Stream">
                        <Button
                          onClick={() => handleCameraSourceChange(camera.id, "mock")}
                          sx={{
                            backgroundColor: camera.stream_url.includes("mock") || camera.stream_url.includes("rtsp") ? "#DDF2FE" : "transparent",
                            borderColor: duoColors.swan,
                          }}
                        >
                          <PlayCircleRoundedIcon fontSize="small" />
                        </Button>
                      </Tooltip>
                    </ButtonGroup>
                  </Box>
                </Grid>
              ))}
          </Grid>
          {/* Hidden File Input for Video Upload */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleVideoUpload}
            accept="video/*"
            style={{ display: "none" }}
          />
        </Card>
      )}

      {/* Main Seat Grid Layout */}
      {loading ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
          <CircularProgress color="primary" />
        </Box>
      ) : filteredSeats.length === 0 ? (
        <Card sx={{ py: 6, textAlign: "center" }}>
          <ChairRoundedIcon sx={{ fontSize: 48, color: duoColors.swan, mb: 1 }} />
          <Typography sx={{ fontWeight: 800, color: duoColors.wolf }}>
            No seats found matching the filters.
          </Typography>
        </Card>
      ) : (
        <Grid container spacing={3}>
          {/* Status Counter Metrics */}
          <Grid item xs={12}>
            <Box sx={{ display: "flex", gap: 3, flexWrap: "wrap", mb: 1 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Box sx={{ width: 14, height: 14, borderRadius: 1.5, bgcolor: "#FFFFFF", border: `2px solid ${duoColors.swan}` }} />
                <Typography variant="body2" sx={{ fontWeight: 800 }}>Vacant ({vacantCount})</Typography>
              </Box>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Box sx={{ width: 14, height: 14, borderRadius: 1.5, bgcolor: "#E6F9D4", border: `2px solid ${duoColors.featherGreen}` }} />
                <Typography variant="body2" sx={{ fontWeight: 800 }}>Occupied ({occupiedCount})</Typography>
              </Box>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Box sx={{ width: 14, height: 14, borderRadius: 1.5, bgcolor: "#FFE0E0", border: `2px solid ${duoColors.cardinal}` }} />
                <Typography variant="body2" sx={{ fontWeight: 800 }}>Over-utilized ({overUtilizedCount})</Typography>
              </Box>
            </Box>
          </Grid>

          {/* Seating Grid */}
          <Grid item xs={12}>
            <Card sx={{ p: 4, bgcolor: "#FFFFFF" }}>
              <Grid container spacing={2}>
                {filteredSeats.map((seat) => {
                  const style = getSeatColor(seat.status, seat);
                  return (
                    <Grid item xs={4} sm={3} md={2} lg={1.5} key={seat.seat_id}>
                      <Tooltip
                        title={
                          <Box sx={{ p: 0.5 }}>
                            <Typography variant="caption" sx={{ fontWeight: 800, display: "block" }}>
                              Seat: {seat.seat_label}
                            </Typography>
                            <Typography variant="caption" sx={{ display: "block" }}>
                              Zone: {seat.zone_name}
                            </Typography>
                            {seat.startup_name && (
                              <Typography variant="caption" sx={{ display: "block", color: duoColors.bee }}>
                                Allocated to: {seat.startup_name}
                              </Typography>
                            )}
                            <Typography variant="caption" sx={{ display: "block" }}>
                              Status: {seat.status}
                            </Typography>
                          </Box>
                        }
                        arrow
                      >
                        <Box
                          sx={{
                            aspectRatio: "1/1",
                            borderRadius: 4,
                            border: `2px solid ${style.border}`,
                            borderBottom: `5px solid ${style.borderBottom}`,
                            backgroundColor: style.bg,
                            display: "flex",
                            flexDirection: "column",
                            justifyContent: "center",
                            alignItems: "center",
                            cursor: "pointer",
                            transition: "all 0.1s ease",
                            "&:active": {
                              transform: "translateY(2px)",
                              borderBottomWidth: "2px",
                            },
                          }}
                        >
                          <ChairRoundedIcon sx={{ color: style.text, fontSize: 28 }} />
                          <Typography sx={{ fontWeight: 900, fontSize: "0.75rem", color: style.text, mt: 0.5 }}>
                            {seat.seat_label}
                          </Typography>
                        </Box>
                      </Tooltip>
                    </Grid>
                  );
                })}
              </Grid>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Feedback Toast */}
      <Snackbar
        open={alert.open}
        autoHideDuration={4000}
        onClose={() => setAlert((prev) => ({ ...prev, open: false }))}
      >
        <Alert severity={alert.severity} variant="filled" sx={{ borderRadius: 3, fontWeight: 700 }}>
          {alert.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
