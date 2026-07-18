import { useState, useEffect, useRef, useCallback } from "react";
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Chip,
  Alert,
  AlertTitle,
  Button,
  CircularProgress,
  Tooltip,
  LinearProgress,
} from "@mui/material";
import PeopleRoundedIcon from "@mui/icons-material/PeopleRounded";
import ChairRoundedIcon from "@mui/icons-material/ChairRounded";
import BusinessRoundedIcon from "@mui/icons-material/BusinessRounded";
import TrendingUpRoundedIcon from "@mui/icons-material/TrendingUpRounded";
import WarningAmberRoundedIcon from "@mui/icons-material/WarningAmberRounded";
import MonetizationOnRoundedIcon from "@mui/icons-material/MonetizationOnRounded";
import SpeedRoundedIcon from "@mui/icons-material/SpeedRounded";
import EmojiEventsRoundedIcon from "@mui/icons-material/EmojiEventsRounded";
import VideocamRoundedIcon from "@mui/icons-material/VideocamRounded";
import UploadFileRoundedIcon from "@mui/icons-material/UploadFileRounded";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as ChartTooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
} from "recharts";

import apiClient, { setAuthToken } from "../../api/client";
import { duoColors } from "../../theme";

// ─── Fallback mock data ───────────────────────────────────────────────────────
const FALLBACK_HOURLY = [
  { hour: "8AM", occupancy: 23 }, { hour: "9AM", occupancy: 45 },
  { hour: "10AM", occupancy: 78 }, { hour: "11AM", occupancy: 82 },
  { hour: "12PM", occupancy: 65 }, { hour: "1PM", occupancy: 58 },
  { hour: "2PM", occupancy: 71 }, { hour: "3PM", occupancy: 76 },
  { hour: "4PM", occupancy: 68 }, { hour: "5PM", occupancy: 42 },
];
const FALLBACK_STARTUPS = [
  { name: "Startup A", allocated: 20, utilized: 14, color: duoColors.featherGreen },
  { name: "Startup B", allocated: 20, utilized: 18, color: duoColors.dodgerBlue },
  { name: "Startup C", allocated: 15, utilized: 8,  color: duoColors.cardinal },
  { name: "Startup D", allocated: 25, utilized: 22, color: duoColors.beetle },
  { name: "Startup E", allocated: 20, utilized: 12, color: duoColors.fox },
];

// ─── Sub-components ───────────────────────────────────────────────────────────
function StatCard({ title, value, subtitle, icon, color, borderColor }) {
  return (
    <Card sx={{ height: "100%", borderColor, borderBottomColor: borderColor }}>
      <CardContent sx={{ p: 2.5 }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <Box sx={{ flex: 1 }}>
            <Typography sx={{ fontSize: "0.72rem", fontWeight: 800, color: duoColors.wolf, letterSpacing: "0.1em", textTransform: "uppercase", mb: 0.5 }}>
              {title}
            </Typography>
            <Typography sx={{ fontWeight: 900, fontSize: "1.8rem", lineHeight: 1.1, color: color }}>
              {value}
            </Typography>
            {subtitle && (
              <Typography sx={{ fontSize: "0.8rem", fontWeight: 600, color: duoColors.hare, mt: 0.5 }}>
                {subtitle}
              </Typography>
            )}
          </Box>
          <Box sx={{ width: 50, height: 50, borderRadius: 3.5, bgcolor: color, display: "flex", alignItems: "center", border: `2px solid ${borderColor}`, borderBottom: `4px solid ${borderColor}`, flexShrink: 0, justifyContent: "center" }}>
            {icon}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}

function DuoTooltip({ active, payload, label, suffix = "%" }) {
  if (!active || !payload?.length) return null;
  return (
    <Box sx={{ bgcolor: duoColors.snow, border: `2px solid ${duoColors.swan}`, borderBottom: `4px solid ${duoColors.swan}`, borderRadius: 3, px: 2, py: 1 }}>
      <Typography sx={{ fontWeight: 800, fontSize: "0.85rem", color: duoColors.eel, mb: 0.5 }}>{label}</Typography>
      {payload.map((p, i) => (
        <Typography key={i} sx={{ fontWeight: 700, fontSize: "0.8rem", color: p.color || duoColors.featherGreen }}>
          {p.name}: {p.value}{suffix}
        </Typography>
      ))}
    </Box>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────
export default function Dashboard() {
  // Connection state
  const [backendOnline, setBackendOnline] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [loading, setLoading] = useState(true);

  // Camera / feed state
  const [activeCameraId, setActiveCameraId] = useState("25548c87-5cdd-464a-9f5c-23220a938530");
  const [activeFeed, setActiveFeed] = useState("mock"); // "mock" | "video"
  const [uploading, setUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [uploadError, setUploadError] = useState("");

  // Session lifecycle states
  const [analysisStatus, setAnalysisStatus] = useState("IDLE"); // "IDLE" | "UPLOADING" | "PROCESSING" | "ANALYZING" | "COMPLETED"
  const [streamSrc, setStreamSrc] = useState("");
  const [sessionId, setSessionId] = useState("");

  // Seat matrix — populated by WS and REST
  const [seats, setSeats] = useState([]);

  // Processing stats from WS
  const [procStats, setProcStats] = useState({ frame: 0, total_frames: 0, fps: 0, stage: "" });

  // Initialization progress
  const [initProgress, setInitProgress] = useState(0);
  const [initTotal, setInitTotal] = useState(150);
  const [initStage, setInitStage] = useState("Detecting physical seats...");

  // Real-time timeline & session analytics
  const [timelineData, setTimelineData] = useState([]);
  const [peakOccupancy, setPeakOccupancy] = useState({ value: 0, time: "0s" });
  const [totalStateChanges, setTotalStateChanges] = useState(0);
  const [averageOccupancySum, setAverageOccupancySum] = useState(0);
  const [processedFramesCount, setProcessedFramesCount] = useState(0);

  // Analytics data
  const [hourlyData, setHourlyData] = useState(FALLBACK_HOURLY);
  const [startupData, setStartupData] = useState(FALLBACK_STARTUPS);

  const fileInputRef = useRef(null);
  const wsRef = useRef(null);
  const imgRef = useRef(null);
  const prevSeatStatusesRef = useRef({});

  // ── Computed KPIs from seat list ─────────────────────────────────────────
  const occupied = seats.filter((s) => s.status === "OCCUPIED").length;
  const vacant = seats.length - occupied;
  const utilPct = seats.length > 0 ? Math.round((occupied / seats.length) * 100) : 0;
  const progressPct = analysisStatus === "COMPLETED"
    ? 100
    : procStats.total_frames > 0
      ? Math.round((procStats.frame / procStats.total_frames) * 100)
      : 0;
  const avgOccupancy = processedFramesCount > 0 ? Math.round(averageOccupancySum / processedFramesCount) : 0;

  // ── Auth helper ──────────────────────────────────────────────────────────
  const ensureAuth = useCallback(async () => {
    const token = localStorage.getItem("workspace_monitor_token");
    if (token) return true;
    try {
      const res = await apiClient.post("/auth/login/json", {
        email: "admin@workspace.dev",
        password: "Admin@12345",
      });
      if (res.access_token) {
        setAuthToken(res.access_token);
        return true;
      }
    } catch { /* silent */ }
    return false;
  }, []);

  // ── Initial data load ────────────────────────────────────────────────────
  useEffect(() => {
    let retried = false;
    const init = async () => {
      await ensureAuth();
      try {
        const buildings = await apiClient.get("/buildings");
        if (!buildings?.length) return;

        setBackendOnline(true);
        const buildingId = buildings[0].id;

        // Building detail → cameras
        const detail = await apiClient.get(`/buildings/${buildingId}`);
        const cameras = detail.cameras || [];
        let initialSeats = [];
        if (cameras.length > 0) {
          const cam = cameras[0];
          setActiveCameraId(cam.id);
          const url = cam.stream_url || "";
          const isVideo = url.includes(".mp4") || url.includes("video") || (cam.config?.source_type === "video");
          if (isVideo) {
            setActiveFeed("video");
            setStreamSrc(`/api/v1/occupancy/camera/${cam.id}/stream`);
          }
          
          try {
            const cameraSeatsRes = await apiClient.get(`/occupancy/camera/${cam.id}/seats`);
            initialSeats = cameraSeatsRes.seats || [];
             if (cameraSeatsRes.session_id) setSessionId(cameraSeatsRes.session_id);
             if (cameraSeatsRes.status) {
               // Do not restore incomplete analysis session after refresh
               if (cameraSeatsRes.status === "COMPLETED") {
                 setAnalysisStatus("COMPLETED");
               } else {
                 setAnalysisStatus("IDLE");
               }
             }
          } catch (e) {
            const liveData = await apiClient.get(`/occupancy/live/${buildingId}`);
            initialSeats = liveData.seats || [];
          }
        } else {
          const liveData = await apiClient.get(`/occupancy/live/${buildingId}`);
          initialSeats = liveData.seats || [];
        }
        setSeats(initialSeats);

        // Startup stats for bar chart
        try {
          const stats = await apiClient.get("/startups/stats");
          if (stats?.length) {
            setStartupData(stats.map((s, idx) => ({
              name: s.startup_name,
              allocated: s.allocated_seats,
              utilized: s.occupied_seats,
              color: [duoColors.featherGreen, duoColors.dodgerBlue, duoColors.cardinal, duoColors.beetle, duoColors.fox][idx % 5],
            })));
          }
        } catch { /* keep fallback */ }

        // Hourly snapshots for area chart
        try {
          const snaps = await apiClient.get("/analytics/snapshots", {
            params: { building_id: buildingId, period_type: "HOURLY", page_size: 10 },
          });
          if (snaps?.items?.length) {
            setHourlyData([...snaps.items].reverse().map((s) => {
              const d = new Date(s.snapshot_time);
              return { hour: d.toLocaleTimeString([], { hour: "numeric" }), occupancy: Math.round(s.occupancy_rate) };
            }));
          }
        } catch { /* keep fallback */ }

      } catch (err) {
        console.error("Init error:", err);
        if (err.status === 401 && !retried) {
          retried = true;
          localStorage.removeItem("workspace_monitor_token");
          await init();
        }
      } finally {
        setLoading(false);
      }
    };
    init();
  }, [ensureAuth]);

  // ── WebSocket setup ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!backendOnline) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    // Always use the Vite proxy path — never hardcode port 8000
    const wsUrl = `${protocol}//${window.location.host}/api/v1/occupancy/ws`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      console.log("WS connected");
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "ping") return;

        if (msg.type === "init_progress") {
          setAnalysisStatus("PROCESSING");
          setInitProgress(msg.frame || 0);
          setInitTotal(msg.total || 150);
          setInitStage(msg.stage || "Detecting physical seats...");
          if (msg.session_id) setSessionId(msg.session_id);
        } else if (msg.type === "status_update") {
          setAnalysisStatus(msg.status);
          if (msg.session_id) setSessionId(msg.session_id);
        } else if (msg.type === "seat_layout") {
          // Authoritative seat list from ChairDetector — replace everything
          // This is sent once after chair detection completes
          const incoming = msg.seats || [];
          setSeats(incoming.map((s) => ({
            seat_id: s.seat_id,
            seat_label: s.label,
            status: s.status || "VACANT",
          })));
          if (msg.session_id) setSessionId(msg.session_id);
          setAnalysisStatus("ANALYZING");
        } else if (msg.type === "seat_update") {
          setSeats((prev) =>
            prev.map((s) =>
              s.seat_id === msg.seat_id ? { ...s, status: msg.status } : s
            )
          );
        } else if (msg.type === "seat_matrix") {
          // Full matrix broadcast from mock mode
          const incoming = msg.seats || [];
          if (incoming.length === 0) return;
          setSeats((prev) => {
            if (prev.length === 0) {
              return incoming.map((s) => ({
                seat_id: s.seat_id || s.label,
                seat_label: s.label,
                status: s.status,
              }));
            }
            const statusMap = Object.fromEntries(
              incoming.map((s) => [s.seat_id || s.label, s.status])
            );
            return prev.map((s) => ({
              ...s,
              status: statusMap[s.seat_id] ?? s.status,
            }));
          });
        } else if (msg.type === "processing_update") {
          setProcStats({
            frame: msg.frame || 0,
            total_frames: msg.total_frames || 0,
            fps: msg.fps || 0,
            stage: msg.stage || "",
          });
          if (msg.status) {
            setAnalysisStatus(msg.status);
          }
          if (msg.session_id) {
            setSessionId(msg.session_id);
          }

          // Update seat statuses from CV results
          const incoming = msg.seats || [];
          if (incoming.length > 0) {
            setSeats((prev) => {
              const updated = prev.length === 0
                ? incoming.map((s) => ({
                    seat_id: s.seat_id,
                    seat_label: s.label,
                    status: s.status,
                  }))
                : prev.map((s) => {
                    const found = incoming.find((inc) => inc.seat_id === s.seat_id);
                    return found ? { ...s, status: found.status } : s;
                  });

              // Incrementally calculate timeline and session metrics
              const seconds = Math.round((msg.frame || 0) / (msg.video_fps || 25));
              const occupiedCount = updated.filter((s) => s.status === "OCCUPIED").length;
              const totalSeatsCount = updated.length;
              const occupancyPct = totalSeatsCount > 0 ? Math.round((occupiedCount / totalSeatsCount) * 100) : 0;

              // Timeline graph update
              setTimelineData((prevTimeline) => {
                if (msg.frame <= 5) {
                  return [{ time: `${seconds}s`, occupancy: occupancyPct, seconds }];
                }
                const idx = prevTimeline.findIndex((d) => d.seconds === seconds);
                if (idx !== -1) {
                  const copy = [...prevTimeline];
                  copy[idx] = { time: `${seconds}s`, occupancy: occupancyPct, seconds };
                  return copy;
                } else {
                  return [...prevTimeline, { time: `${seconds}s`, occupancy: occupancyPct, seconds }].sort((a, b) => a.seconds - b.seconds);
                }
              });

              // Peak occupancy update
              setPeakOccupancy((prevPeak) => {
                if (occupancyPct > prevPeak.value) {
                  return { value: occupancyPct, time: `${seconds}s` };
                }
                return prevPeak;
              });

              // State changes count
              let stateChanges = 0;
              const prevStatuses = prevSeatStatusesRef.current;
              updated.forEach((s) => {
                const prevStatus = prevStatuses[s.seat_id];
                if (prevStatus && prevStatus !== s.status) {
                  stateChanges += 1;
                }
                prevStatuses[s.seat_id] = s.status;
              });
              if (stateChanges > 0) {
                setTotalStateChanges((c) => c + stateChanges);
              }

              // Average occupancy aggregation
              setAverageOccupancySum((sum) => sum + occupancyPct);
              setProcessedFramesCount((count) => count + 1);

              return updated;
            });
          }
        }
      } catch (e) {
        console.error("WS parse error:", e);
      }
    };

    ws.onerror = () => setWsConnected(false);
    ws.onclose = () => setWsConnected(false);

    return () => ws.close();
  }, [backendOnline]);

  // ── Video upload handler ──────────────────────────────────────────────────
  const handleVideoUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    await ensureAuth();
    setUploading(true);
    setUploadSuccess(false);
    setUploadError("");
    setAnalysisStatus("UPLOADING");
    setSessionId("");
    setSeats([]);
    setStreamSrc("");
    setProcStats({ frame: 0, total_frames: 0, fps: 0, stage: "" });
    setInitProgress(0);
    setInitStage("Detecting physical seats...");
    setTimelineData([]);
    setPeakOccupancy({ value: 0, time: "0s" });
    setTotalStateChanges(0);
    setAverageOccupancySum(0);
    setProcessedFramesCount(0);
    prevSeatStatusesRef.current = {};

    const formData = new FormData();
    formData.append("file", file);

    try {
      await apiClient.post(`/occupancy/camera/${activeCameraId}/upload-video`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 0, // Bypass default global Axios timeout for large video uploads
      });
      setActiveFeed("video");
      setUploadSuccess(true);
      setAnalysisStatus("PROCESSING");
      setStreamSrc(`/api/v1/occupancy/camera/${activeCameraId}/stream?t=${Date.now()}`);
    } catch (err) {
      console.error("Upload error:", err);
      setUploadError(err?.message || "Unknown error during upload.");
      setAnalysisStatus("IDLE");
    } finally {
      setUploading(false);
      event.target.value = null;
    }
  };

  // ── Seat tile helper ─────────────────────────────────────────────────────
  const getSeatStyle = (status) =>
    status === "OCCUPIED"
      ? { bg: "#DDF2FE", border: duoColors.dodgerBlue, text: duoColors.dodgerBlueDark }
      : { bg: "#E8F9E0", border: duoColors.featherGreen, text: duoColors.featherGreenDark };

  const getStatusLabel = (status) => {
    switch (status) {
      case "UPLOADING": return "Uploading";
      case "PROCESSING": return "Processing";
      case "ANALYZING": return "Analyzing";
      case "COMPLETED": return "Completed";
      default: return "Idle";
    }
  };

  const isOnline = backendOnline || wsConnected;

  return (
    <Box>
      {/* ── Header ── */}
      <Box sx={{ mb: 3, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 2 }}>
        <Box>
          <Typography variant="h3" sx={{ fontWeight: 900, color: duoColors.eel }}>
            AI Workspace Monitor
          </Typography>
          <Typography sx={{ fontSize: "0.95rem", fontWeight: 600, color: duoColors.wolf }}>
            Real-time occupancy tracking powered by computer vision
          </Typography>
        </Box>
        <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
          <Chip
            icon={wsConnected ? <CheckCircleRoundedIcon /> : undefined}
            label={wsConnected ? "LIVE STREAM" : "OFFLINE"}
            color={wsConnected ? "success" : "default"}
            sx={{ fontWeight: 800 }}
          />
          <Chip
            label={`${activeFeed.toUpperCase()} MODE`}
            color={activeFeed === "video" ? "primary" : "default"}
            sx={{ fontWeight: 800 }}
          />
        </Box>
      </Box>

      {!isOnline && !loading && (
        <Alert severity="warning" icon={<WarningAmberRoundedIcon />} sx={{ mb: 3 }}>
          <AlertTitle sx={{ fontWeight: 800 }}>Backend Offline</AlertTitle>
          Cannot reach FastAPI at localhost:8000. Showing fallback data.
        </Alert>
      )}

      {uploadSuccess && (
        <Alert severity="success" icon={<CheckCircleRoundedIcon />} sx={{ mb: 3 }} onClose={() => setUploadSuccess(false)}>
          <AlertTitle sx={{ fontWeight: 800 }}>Processing Started</AlertTitle>
          Video uploaded. YOLO analysis is running — the stream and seat matrix will update live.
        </Alert>
      )}

      {uploadError && (
        <Alert severity="error" icon={<WarningAmberRoundedIcon />} sx={{ mb: 3 }} onClose={() => setUploadError("")}>
          <AlertTitle sx={{ fontWeight: 800 }}>Upload Failed</AlertTitle>
          {uploadError}
        </Alert>
      )}

      {/* ── Main 70/30 Split ── */}
      <Grid container spacing={3} sx={{ mb: 3 }}>

        {/* Left 70% — Video Player + Stats */}
        <Grid item xs={12} md={8}>

          {/* Video Player Card */}
          <Card sx={{ mb: 2, bgcolor: "#111", position: "relative", overflow: "hidden", borderRadius: 3 }}>
            {/* Upload button — always visible */}
            <Box sx={{ position: "absolute", top: 12, right: 12, zIndex: 20 }}>
              <Button
                variant="contained"
                size="small"
                startIcon={uploading ? <CircularProgress size={14} color="inherit" /> : <UploadFileRoundedIcon />}
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                sx={{
                  bgcolor: "rgba(30,30,30,0.85)",
                  color: "#FFF",
                  fontWeight: 800,
                  backdropFilter: "blur(6px)",
                  border: "1px solid rgba(255,255,255,0.2)",
                  "&:hover": { bgcolor: duoColors.dodgerBlue },
                  "&:disabled": { bgcolor: "rgba(30,30,30,0.5)", color: "rgba(255,255,255,0.4)" },
                }}
              >
                {uploading ? "Uploading…" : "Upload Video"}
              </Button>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleVideoUpload}
                accept="video/*"
                style={{ display: "none" }}
              />
            </Box>

            {/* Feed mode badge */}
            <Box sx={{ position: "absolute", top: 12, left: 12, zIndex: 20 }}>
              <Chip
                size="small"
                label={wsConnected ? "● LIVE" : "● WAITING"}
                sx={{
                  bgcolor: wsConnected ? "rgba(88,204,2,0.85)" : "rgba(80,80,80,0.85)",
                  color: "#FFF",
                  fontWeight: 900,
                  fontSize: "0.7rem",
                  backdropFilter: "blur(6px)",
                }}
              />
            </Box>

            {/* Overlays */}
            {(analysisStatus === "UPLOADING" || analysisStatus === "INITIALIZING" || analysisStatus === "PROCESSING") && (
              <Box
                sx={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  height: "100%",
                  bgcolor: "rgba(10, 10, 10, 0.88)",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  zIndex: 15,
                  backdropFilter: "blur(8px)",
                }}
              >
                <CircularProgress size={48} sx={{ color: duoColors.dodgerBlue, mb: 3 }} />
                <Typography variant="h6" sx={{ color: "#FFF", fontWeight: 800 }}>
                  {analysisStatus === "UPLOADING" 
                    ? "Uploading Video..." 
                    : analysisStatus === "INITIALIZING"
                      ? "Initializing Analysis..."
                      : "Detecting Workspace Layout..."}
                </Typography>
                
                {analysisStatus === "PROCESSING" && (
                  <Box sx={{ width: "80%", maxWidth: 320, mt: 2.5, textAlign: "center" }}>
                    <LinearProgress
                      variant="determinate"
                      value={Math.round((initProgress / initTotal) * 100)}
                      sx={{
                        height: 6,
                        borderRadius: 3,
                        bgcolor: "rgba(255,255,255,0.1)",
                        "& .MuiLinearProgress-bar": { borderRadius: 3, bgcolor: duoColors.dodgerBlue },
                        mb: 1
                      }}
                    />
                    <Typography variant="caption" sx={{ color: "#AAA", fontWeight: 700 }}>
                      {initStage} ({Math.round((initProgress / initTotal) * 100)}%)
                    </Typography>
                    <Typography variant="body2" sx={{ color: "rgba(255,255,255,0.4)", fontSize: "0.75rem", mt: 0.5 }}>
                      Processed {initProgress} of {initTotal} setup frames
                    </Typography>
                  </Box>
                )}

                {analysisStatus !== "PROCESSING" && (
                  <Typography variant="body2" sx={{ color: "#AAA", mt: 1, px: 4, textAlign: "center", maxWidth: 360 }}>
                    {analysisStatus === "UPLOADING" 
                      ? "Transferring high-definition video to the computer vision backend."
                      : "Creating a new analysis session and allocating worker resources."}
                  </Typography>
                )}
              </Box>
            )}

            {analysisStatus === "COMPLETED" && (
              <Box
                sx={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  height: "100%",
                  bgcolor: "rgba(0, 0, 0, 0.75)",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  zIndex: 15,
                  backdropFilter: "blur(4px)",
                }}
              >
                <Box
                  sx={{
                    bgcolor: "rgba(25, 25, 25, 0.95)",
                    border: `2px solid ${duoColors.featherGreen}`,
                    borderBottom: `4px solid ${duoColors.featherGreen}`,
                    borderRadius: 4,
                    p: 4,
                    textAlign: "center",
                    maxWidth: 380,
                    boxShadow: "0 12px 40px rgba(0,0,0,0.6)",
                  }}
                >
                  <CheckCircleRoundedIcon sx={{ fontSize: 56, color: duoColors.featherGreen, mb: 2 }} />
                  <Typography variant="h5" sx={{ color: "#FFF", fontWeight: 900, mb: 1, letterSpacing: "-0.01em" }}>
                    Analysis Complete
                  </Typography>
                  <Typography variant="body2" sx={{ color: "#CCC", mb: 0, fontWeight: 500 }}>
                    Upload another video to begin a new analysis.
                  </Typography>
                </Box>
              </Box>
            )}

            {/* MJPEG stream image — shown when video mode is active */}
            {activeFeed === "video" && activeCameraId ? (
              <Box sx={{ width: "100%", minHeight: 420, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", position: "relative" }}>
                {streamSrc && (
                  <img
                    ref={imgRef}
                    src={streamSrc}
                    alt="Live AI Processing Stream"
                    style={{
                      width: "100%",
                      maxHeight: 520,
                      objectFit: "contain",
                      display: "block",
                    }}
                    onError={() => {
                      // Stream not ready yet — retry after 2 seconds
                      setTimeout(() => {
                        if (imgRef.current) {
                          imgRef.current.src = `${streamSrc}&retry=${Date.now()}`;
                        }
                      }, 2000);
                    }}
                  />
                )}
                
                {/* Live Processing Stage Ticker (Step 5) */}
                {analysisStatus === "ANALYZING" && procStats.total_frames > 0 && (
                  <Box
                    sx={{
                      position: "absolute",
                      bottom: 0,
                      left: 0,
                      width: "100%",
                      bgcolor: "rgba(20, 20, 20, 0.85)",
                      py: 1.2,
                      px: 2.5,
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      borderTop: "1px solid rgba(255,255,255,0.15)",
                      backdropFilter: "blur(6px)",
                      zIndex: 10,
                    }}
                  >
                    <Typography sx={{ color: "#FFF", fontSize: "0.78rem", fontWeight: 800, letterSpacing: "0.02em" }}>
                      Analyzing Frame {procStats.frame} / {procStats.total_frames}
                    </Typography>
                    <Typography sx={{ color: duoColors.dodgerBlue, fontSize: "0.78rem", fontWeight: 900, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                      ● {procStats.stage || "Detecting Occupancy..."}
                    </Typography>
                  </Box>
                )}
              </Box>
            ) : (
              <Box sx={{ minHeight: 420, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "#AAA" }}>
                <VideocamRoundedIcon sx={{ fontSize: 72, opacity: 0.3, mb: 2 }} />
                <Typography variant="h6" sx={{ opacity: 0.5, fontWeight: 700 }}>No Video Feed Active</Typography>
                <Typography variant="body2" sx={{ opacity: 0.35, mt: 0.5 }}>
                  Click "Upload Video" to begin AI processing
                </Typography>
                {backendOnline && activeFeed === "mock" && (
                  <Typography variant="body2" sx={{ mt: 1.5, color: duoColors.featherGreen, fontWeight: 700, opacity: 0.8 }}>
                    ✓ Mock simulation running — seat matrix is updating live
                  </Typography>
                )}
              </Box>
            )}
          </Card>

          {/* Processing Statistics Bar */}
          <Card sx={{ p: 3 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 900, color: duoColors.eel, mb: 2 }}>
              Processing Statistics
            </Typography>

            {/* Progress bar */}
            <Box sx={{ mb: 2.5 }}>
              <Box sx={{ display: "flex", justifyContent: "space-between", mb: 0.8 }}>
                <Typography variant="caption" sx={{ fontWeight: 700, color: duoColors.wolf }}>
                  {procStats.total_frames > 0 ? `Frame ${procStats.frame} of ${procStats.total_frames}` : "Waiting for frames…"}
                </Typography>
                <Typography variant="caption" sx={{ fontWeight: 800, color: duoColors.dodgerBlue }}>
                  {progressPct}%
                </Typography>
              </Box>
              <LinearProgress
                variant="determinate"
                value={progressPct}
                sx={{
                  height: 8,
                  borderRadius: 4,
                  bgcolor: duoColors.snow,
                  "& .MuiLinearProgress-bar": { borderRadius: 4, bgcolor: duoColors.dodgerBlue },
                }}
              />
            </Box>

            <Grid container spacing={2}>
              {[
                { label: "Status", value: getStatusLabel(analysisStatus), color: analysisStatus === "COMPLETED" ? duoColors.featherGreen : duoColors.dodgerBlue },
                { label: "Processing FPS", value: `${procStats.fps} fps`, color: duoColors.dodgerBlue },
                { label: "Frames Processed", value: procStats.frame, color: duoColors.eel },
                { label: "Occupied", value: occupied, color: duoColors.dodgerBlueDark },
                { label: "Vacant", value: vacant, color: duoColors.featherGreenDark },
                { label: "Utilization", value: `${utilPct}%`, color: utilPct > 70 ? duoColors.cardinal : duoColors.featherGreen },
              ].map(({ label, value, color }) => (
                <Grid item xs={6} sm={4} md={2} key={label}>
                  <Typography sx={{ color: duoColors.hare, fontSize: "0.72rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    {label}
                  </Typography>
                  <Typography sx={{ fontWeight: 900, fontSize: "1.3rem", color }}>
                    {value}
                  </Typography>
                </Grid>
              ))}
            </Grid>
          </Card>
        </Grid>

        {/* Right 30% — Live Seat Matrix */}
        <Grid item xs={12} md={4}>
          <Card sx={{ p: 3, height: "100%", display: "flex", flexDirection: "column", maxHeight: 680 }}>
            {/* Header */}
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 1.5 }}>
              <Typography variant="h6" sx={{ fontWeight: 900 }}>Live Seat Matrix</Typography>
              <Chip
                size="small"
                label={wsConnected ? "LIVE" : "STATIC"}
                color={wsConnected ? "success" : "default"}
                sx={{ fontWeight: 800 }}
              />
            </Box>

            {/* Legend */}
            <Box sx={{ display: "flex", gap: 2, mb: 2 }}>
              {[
                { color: "#DDF2FE", border: duoColors.dodgerBlue, label: `Occupied (${occupied})` },
                { color: "#E8F9E0", border: duoColors.featherGreen, label: `Vacant (${vacant})` },
              ].map(({ color, border, label }) => (
                <Box key={label} sx={{ display: "flex", alignItems: "center", gap: 0.8 }}>
                  <Box sx={{ width: 12, height: 12, bgcolor: color, border: `2px solid ${border}`, borderRadius: 1, flexShrink: 0 }} />
                  <Typography variant="caption" sx={{ fontWeight: 700, color: duoColors.wolf }}>{label}</Typography>
                </Box>
              ))}
            </Box>

            {/* Seat tiles */}
            <Box sx={{ flexGrow: 1, overflowY: "auto", pr: 0.5 }}>
              {loading ? (
                <Box sx={{ py: 8, textAlign: "center" }}>
                  <CircularProgress size={32} sx={{ mb: 2 }} />
                  <Typography sx={{ fontWeight: 700, color: duoColors.wolf }}>Loading seats…</Typography>
                </Box>
              ) : seats.length === 0 ? (
                <Box sx={{ py: 8, textAlign: "center" }}>
                  <Typography sx={{ fontWeight: 700, color: duoColors.hare }}>No seats configured</Typography>
                  <Typography variant="caption" sx={{ color: duoColors.hare }}>
                    Seats will appear once the backend returns data
                  </Typography>
                </Box>
              ) : (
                <Grid container spacing={0.8}>
                  {seats.map((seat) => {
                    const s = getSeatStyle(seat.status);
                    const label = seat.seat_label || seat.label || "?";
                    const id = seat.seat_id || seat.id || label;
                    return (
                      <Grid item xs={4} sm={3} md={4} key={id}>
                        <Tooltip title={`${label} — ${seat.status || "VACANT"}`} arrow placement="top">
                          <Box
                            sx={{
                              p: 0.8,
                              borderRadius: 1.5,
                              border: `2px solid ${s.border}`,
                              bgcolor: s.bg,
                              display: "flex",
                              flexDirection: "column",
                              alignItems: "center",
                              gap: 0.3,
                              transition: "background-color 0.3s ease, border-color 0.3s ease",
                              cursor: "default",
                              "&:hover": { opacity: 0.8 },
                            }}
                          >
                            <ChairRoundedIcon sx={{ color: s.text, fontSize: 16 }} />
                            <Typography sx={{ fontWeight: 900, fontSize: "0.65rem", color: s.text, lineHeight: 1, textAlign: "center" }}>
                              {label}
                            </Typography>
                          </Box>
                        </Tooltip>
                      </Grid>
                    );
                  })}
                </Grid>
              )}
            </Box>

            {/* Utilization bar */}
            {seats.length > 0 && (
              <Box sx={{ mt: 2, pt: 2, borderTop: `1px solid ${duoColors.swan}` }}>
                <Box sx={{ display: "flex", justifyContent: "space-between", mb: 0.5 }}>
                  <Typography variant="caption" sx={{ fontWeight: 700, color: duoColors.wolf }}>Overall Utilization</Typography>
                  <Typography variant="caption" sx={{ fontWeight: 900, color: duoColors.dodgerBlue }}>{utilPct}%</Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={utilPct}
                  sx={{
                    height: 6,
                    borderRadius: 3,
                    bgcolor: "#E8F9E0",
                    "& .MuiLinearProgress-bar": {
                      borderRadius: 3,
                      bgcolor: utilPct > 80 ? duoColors.cardinal : utilPct > 50 ? duoColors.dodgerBlue : duoColors.featherGreen,
                    },
                  }}
                />
              </Box>
            )}
          </Card>
        </Grid>
      </Grid>

      {/* ── KPI Cards ── */}
      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        {activeFeed === "video" ? (
          <>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard title="Current Occupancy" value={`${utilPct}%`} subtitle={`${occupied} / ${seats.length} seats`} icon={<PeopleRoundedIcon sx={{ color: "#FFF", fontSize: 24 }} />} color={duoColors.featherGreen} borderColor={duoColors.featherGreenDark} />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard title="Avg Occupancy" value={`${avgOccupancy}%`} subtitle="Workspace Utilization Score" icon={<BusinessRoundedIcon sx={{ color: "#FFF", fontSize: 24 }} />} color={duoColors.dodgerBlue} borderColor={duoColors.dodgerBlueDark} />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard title="Peak Occupancy" value={`${peakOccupancy.value}%`} subtitle={`at ${peakOccupancy.time}`} icon={<MonetizationOnRoundedIcon sx={{ color: "#FFF", fontSize: 24 }} />} color={duoColors.cardinal} borderColor={duoColors.cardinalDark} />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard title="State Changes" value={totalStateChanges} subtitle="Seat occupancy event count" icon={<SpeedRoundedIcon sx={{ color: "#FFF", fontSize: 24 }} />} color={duoColors.fox} borderColor={duoColors.foxDark} />
            </Grid>
          </>
        ) : (
          <>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard title="Occupancy Rate" value={`${utilPct}%`} subtitle={`${occupied} / ${seats.length} seats`} icon={<PeopleRoundedIcon sx={{ color: "#FFF", fontSize: 24 }} />} color={duoColors.featherGreen} borderColor={duoColors.featherGreenDark} />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard title="Total Startups" value={startupData.length} subtitle="across building" icon={<BusinessRoundedIcon sx={{ color: "#FFF", fontSize: 24 }} />} color={duoColors.dodgerBlue} borderColor={duoColors.dodgerBlueDark} />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard title="Revenue Leakage" value={`$${((vacant * 500) / 1000).toFixed(1)}K`} subtitle="est. monthly from empty seats" icon={<MonetizationOnRoundedIcon sx={{ color: "#FFF", fontSize: 24 }} />} color={duoColors.cardinal} borderColor={duoColors.cardinalDark} />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard title="Processing Speed" value={`${procStats.fps} fps`} subtitle="YOLO inference rate" icon={<SpeedRoundedIcon sx={{ color: "#FFF", fontSize: 24 }} />} color={duoColors.fox} borderColor={duoColors.foxDark} />
            </Grid>
          </>
        )}
      </Grid>

      {/* ── Charts ── */}
      <Grid container spacing={2.5}>
        <Grid item xs={12} md={7}>
          <Card sx={{ p: 2.5 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2.5 }}>
              <TrendingUpRoundedIcon sx={{ color: duoColors.featherGreen, fontSize: 22 }} />
              <Typography sx={{ fontWeight: 800, fontSize: "1rem", color: duoColors.eel }}>
                {activeFeed === "video" ? "Workspace Utilization Timeline" : "Today's Utilization Trend"}
              </Typography>
            </Box>
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={activeFeed === "video" ? timelineData : hourlyData}>
                <defs>
                  <linearGradient id="greenGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={duoColors.featherGreen} stopOpacity={0.25} />
                    <stop offset="95%" stopColor={duoColors.featherGreen} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={duoColors.swan} />
                <XAxis dataKey={activeFeed === "video" ? "time" : "hour"} tick={{ fontSize: 11, fontWeight: 700, fill: duoColors.hare }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fontWeight: 700, fill: duoColors.hare }} axisLine={false} tickLine={false} domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
                <ChartTooltip content={<DuoTooltip />} />
                <Area type="monotone" dataKey="occupancy" name="Occupancy" stroke={duoColors.featherGreen} strokeWidth={3} fill="url(#greenGrad)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </Card>
        </Grid>

        <Grid item xs={12} md={5}>
          <Card sx={{ p: 2.5 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2.5 }}>
              <EmojiEventsRoundedIcon sx={{ color: duoColors.bee, fontSize: 22 }} />
              <Typography sx={{ fontWeight: 800, fontSize: "1rem", color: duoColors.eel }}>Startup Allocations</Typography>
            </Box>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={startupData} layout="vertical" barCategoryGap="25%">
                <CartesianGrid strokeDasharray="3 3" stroke={duoColors.swan} horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fontWeight: 700, fill: duoColors.hare }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fontWeight: 700, fill: duoColors.eel }} axisLine={false} tickLine={false} width={80} />
                <ChartTooltip content={<DuoTooltip suffix="" />} />
                <Bar dataKey="allocated" name="Allocated" fill={duoColors.swan} radius={[0, 8, 8, 0]} barSize={12} />
                <Bar dataKey="utilized" name="Utilized" radius={[0, 8, 8, 0]} barSize={12}>
                  {startupData.map((entry, i) => (
                    <Cell key={`c-${i}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
