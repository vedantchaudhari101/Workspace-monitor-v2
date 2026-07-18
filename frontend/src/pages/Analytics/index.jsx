import { useState, useEffect } from "react";
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
  CircularProgress,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  ToggleButton,
  ToggleButtonGroup,
} from "@mui/material";

// Icons
import SpeedRoundedIcon from "@mui/icons-material/SpeedRounded";
import CalendarMonthRoundedIcon from "@mui/icons-material/CalendarMonthRounded";
import ShowChartRoundedIcon from "@mui/icons-material/ShowChartRounded";
import BarChartRoundedIcon from "@mui/icons-material/BarChartRounded";
import PieChartRoundedIcon from "@mui/icons-material/PieChartRounded";
import TimelineRoundedIcon from "@mui/icons-material/TimelineRounded";
import TableRowsRoundedIcon from "@mui/icons-material/TableRowsRounded";
import SettingsSuggestRoundedIcon from "@mui/icons-material/SettingsSuggestRounded";

import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

import apiClient from "../../api/client";
import { duoColors } from "../../theme";

// Helper to format timestamps for charts
const formatTimeLabel = (timeStr) => {
  if (!timeStr) return "";
  const date = new Date(timeStr);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

const formatFullDateTime = (timeStr) => {
  if (!timeStr) return "";
  const date = new Date(timeStr);
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

const formatDuration = (seconds) => {
  if (seconds === undefined || seconds === null) return "0s";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  
  const parts = [];
  if (h > 0) parts.push(`${h}h`);
  if (m > 0) parts.push(`${m}m`);
  if (s > 0 || parts.length === 0) parts.push(`${s}s`);
  return parts.join(" ");
};

// Custom Tooltip (Duolingo Style)
function ChartTooltip({ active, payload, label, suffix = "%" }) {
  if (!active || !payload?.length) return null;
  return (
    <Box
      sx={{
        bgcolor: duoColors.snow,
        border: `2px solid ${duoColors.swan}`,
        borderBottom: `4px solid ${duoColors.swan}`,
        borderRadius: 3,
        px: 2,
        py: 1.2,
      }}
    >
      <Typography sx={{ fontWeight: 800, fontSize: "0.85rem", color: duoColors.eel, mb: 0.5 }}>
        {formatFullDateTime(label)}
      </Typography>
      {payload.map((p, i) => (
        <Typography
          key={i}
          sx={{
            fontWeight: 700,
            fontSize: "0.8rem",
            color: p.color || duoColors.featherGreen,
          }}
        >
          {p.name}: {p.value.toFixed(1)}{suffix}
        </Typography>
      ))}
    </Box>
  );
}

export default function Analytics() {
  const [buildings, setBuildings] = useState([]);
  const [selectedBuilding, setSelectedBuilding] = useState("");
  const [timeRange, setTimeRange] = useState(24); // default 24 hours
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Fetch all buildings on mount
  useEffect(() => {
    const fetchBuildings = async () => {
      try {
        const buildingsData = await apiClient.get("/buildings");
        setBuildings(buildingsData);
        if (buildingsData.length > 0) {
          setSelectedBuilding(buildingsData[0].id);
        }
      } catch (err) {
        setError("Failed to fetch buildings configuration");
      }
    };
    fetchBuildings();
  }, []);

  // Fetch comprehensive analytics when building or time range changes
  useEffect(() => {
    if (!selectedBuilding) return;

    const fetchAnalytics = async () => {
      setLoading(true);
      setError("");
      try {
        const analyticsData = await apiClient.get(`/analytics/comprehensive/${selectedBuilding}`, {
          params: { range_hours: timeRange }
        });
        setData(analyticsData);
      } catch (err) {
        console.error("Failed to fetch comprehensive analytics:", err);
        setError("Could not load occupancy analytics. Please verify server connection.");
      } finally {
        setLoading(false);
      }
    };

    fetchAnalytics();
  }, [selectedBuilding, timeRange]);

  const handleTimeRangeChange = (event, newRange) => {
    if (newRange !== null) {
      setTimeRange(newRange);
    }
  };

  const hasTimelineData = data && data.timeline && data.timeline.length > 0;
  const hasSeatData = data && data.seat_stats && data.seat_stats.length > 0;

  // Pie chart data
  const pieData = data ? [
    { name: "Occupied Time", value: data.distribution.occupied_pct, color: duoColors.fox },
    { name: "Vacant Time", value: data.distribution.vacant_pct, color: duoColors.featherGreen },
  ] : [];

  return (
    <Box sx={{ pb: 6 }}>
      {/* Header & Controls */}
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 4, flexWrap: "wrap", gap: 2 }}>
        <Box>
          <Typography variant="h3" sx={{ fontWeight: 900, color: duoColors.eel }}>
            Workspace Analytics
          </Typography>
          <Typography variant="body1" sx={{ color: duoColors.wolf, mt: 0.5 }}>
            Detailed seat utilization and system execution performance logs
          </Typography>
        </Box>
        
        <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
          {/* Time Range Selector */}
          <ToggleButtonGroup
            value={timeRange}
            exclusive
            onChange={handleTimeRangeChange}
            size="small"
            sx={{
              bgcolor: duoColors.snow,
              borderRadius: 3,
              border: `2px solid ${duoColors.swan}`,
              borderBottom: `4px solid ${duoColors.swan}`,
              p: 0.5,
              "& .MuiToggleButton-root": {
                border: "none",
                borderRadius: 2,
                px: 2,
                fontWeight: 700,
                fontFamily: "Nunito",
                color: duoColors.wolf,
                "&.Mui-selected": {
                  bgcolor: duoColors.featherGreen,
                  color: "#FFF",
                  "&:hover": {
                    bgcolor: duoColors.featherGreenDark,
                  }
                }
              }
            }}
          >
            <ToggleButton value={6}>6H</ToggleButton>
            <ToggleButton value={12}>12H</ToggleButton>
            <ToggleButton value={24}>24H</ToggleButton>
            <ToggleButton value={168}>7D</ToggleButton>
          </ToggleButtonGroup>

          {/* Building Selector */}
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel sx={{ fontFamily: "Nunito", fontWeight: 700 }}>Building</InputLabel>
            <Select
              value={selectedBuilding}
              label="Building"
              onChange={(e) => setSelectedBuilding(e.target.value)}
              sx={{
                borderRadius: 3,
                fontWeight: 700,
                fontFamily: "Nunito",
                bgcolor: "#FFF",
                borderBottom: `2px solid ${duoColors.swan}`,
              }}
            >
              {buildings.map((b) => (
                <MenuItem key={b.id} value={b.id} sx={{ fontFamily: "Nunito", fontWeight: 700 }}>
                  {b.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 4, borderRadius: 3 }}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "40vh" }}>
          <CircularProgress size={50} thickness={5} sx={{ color: duoColors.featherGreen }} />
        </Box>
      ) : !data ? (
        <Card sx={{ p: 4, textAlign: "center", borderRadius: 4, borderBottom: `4px solid ${duoColors.swan}` }}>
          <Typography sx={{ fontWeight: 800, color: duoColors.wolf }}>No data loaded for this building.</Typography>
        </Card>
      ) : (
        <Grid container spacing={3}>
          {/* ==========================================
              SECTION 1: KPI CARDS ROW
             ========================================== */}
          <Grid item xs={12}>
            <Grid container spacing={2.5}>
              <Grid item xs={12} sm={6} md={3} lg={1.71}>
                <Card sx={{ borderColor: duoColors.dodgerBlue, borderBottomWidth: 4 }}>
                  <CardContent sx={{ p: 2 }}>
                    <Typography variant="overline" sx={{ color: duoColors.wolf, fontWeight: 700 }}>Total Seats</Typography>
                    <Typography variant="h3" sx={{ color: duoColors.dodgerBlueDark, mt: 0.5 }}>{data.kpi.total_seats}</Typography>
                  </CardContent>
                </Card>
              </Grid>
              
              <Grid item xs={12} sm={6} md={3} lg={1.71}>
                <Card sx={{ borderColor: duoColors.fox, borderBottomWidth: 4 }}>
                  <CardContent sx={{ p: 2 }}>
                    <Typography variant="overline" sx={{ color: duoColors.wolf, fontWeight: 700 }}>Occupied</Typography>
                    <Typography variant="h3" sx={{ color: duoColors.foxDark, mt: 0.5 }}>{data.kpi.occupied_seats}</Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} sm={6} md={3} lg={1.71}>
                <Card sx={{ borderColor: duoColors.featherGreen, borderBottomWidth: 4 }}>
                  <CardContent sx={{ p: 2 }}>
                    <Typography variant="overline" sx={{ color: duoColors.wolf, fontWeight: 700 }}>Vacant</Typography>
                    <Typography variant="h3" sx={{ color: duoColors.featherGreenDark, mt: 0.5 }}>{data.kpi.vacant_seats}</Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} sm={6} md={3} lg={1.71}>
                <Card sx={{ borderColor: duoColors.beetle, borderBottomWidth: 4 }}>
                  <CardContent sx={{ p: 2 }}>
                    <Typography variant="overline" sx={{ color: duoColors.wolf, fontWeight: 700 }}>Current %</Typography>
                    <Typography variant="h3" sx={{ color: duoColors.beetleDark, mt: 0.5 }}>{data.kpi.current_occupancy_pct}%</Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} sm={6} md={3} lg={1.71}>
                <Card sx={{ borderColor: duoColors.fox, borderBottomWidth: 4 }}>
                  <CardContent sx={{ p: 2 }}>
                    <Typography variant="overline" sx={{ color: duoColors.wolf, fontWeight: 700 }}>Avg %</Typography>
                    <Typography variant="h3" sx={{ color: duoColors.foxDark, mt: 0.5 }}>{data.kpi.avg_occupancy_pct}%</Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} sm={6} md={3} lg={1.71}>
                <Card sx={{ borderColor: duoColors.bee, borderBottomWidth: 4 }}>
                  <CardContent sx={{ p: 2 }}>
                    <Typography variant="overline" sx={{ color: duoColors.wolf, fontWeight: 700 }}>Max %</Typography>
                    <Typography variant="h3" sx={{ color: duoColors.beeDark, mt: 0.5 }}>{data.kpi.max_occupancy_pct}%</Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} sm={6} md={3} lg={1.71}>
                <Card sx={{ borderColor: duoColors.wolf, borderBottomWidth: 4 }}>
                  <CardContent sx={{ p: 2 }}>
                    <Typography variant="overline" sx={{ color: duoColors.wolf, fontWeight: 700 }}>Min %</Typography>
                    <Typography variant="h3" sx={{ color: duoColors.wolfDark, mt: 0.5 }}>{data.kpi.min_occupancy_pct}%</Typography>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </Grid>

          {/* ==========================================
              SECTION 2: OCCUPANCY TIMELINE
             ========================================== */}
          <Grid item xs={12} lg={8}>
            <Card sx={{ p: 3, height: "100%" }}>
              <Box sx={{ mb: 3, display: "flex", alignItems: "center", gap: 1.5 }}>
                <TimelineRoundedIcon sx={{ color: duoColors.dodgerBlue, fontSize: 28 }} />
                <Box>
                  <Typography variant="h5" sx={{ fontWeight: 800 }}>Occupancy Timeline</Typography>
                  <Typography variant="body2" sx={{ color: duoColors.wolf }}>Reconstructed occupancy rate trends over the analysis window</Typography>
                </Box>
              </Box>

              {!hasTimelineData ? (
                <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: 300 }}>
                  <Typography sx={{ color: duoColors.wolf, fontWeight: 700 }}>No timeline data available</Typography>
                </Box>
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={data.timeline} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorOcc" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={duoColors.dodgerBlue} stopOpacity={0.3}/>
                        <stop offset="95%" stopColor={duoColors.dodgerBlue} stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={duoColors.swan} vertical={false} />
                    <XAxis
                      dataKey="time"
                      tickFormatter={formatTimeLabel}
                      stroke={duoColors.wolf}
                      tick={{ fontFamily: "Nunito", fontWeight: 700, fontSize: "0.75rem" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      stroke={duoColors.wolf}
                      tick={{ fontFamily: "Nunito", fontWeight: 700, fontSize: "0.75rem" }}
                      domain={[0, 100]}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip content={<ChartTooltip suffix="%" />} />
                    <Area
                      name="Occupancy"
                      type="monotone"
                      dataKey="occupancy_pct"
                      stroke={duoColors.dodgerBlue}
                      strokeWidth={3}
                      fillOpacity={1}
                      fill="url(#colorOcc)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </Card>
          </Grid>

          {/* ==========================================
              SECTION 4 & 5: DISTRIBUTION & PEAK
             ========================================== */}
          <Grid item xs={12} lg={4}>
            <Grid container spacing={3} sx={{ height: "100%" }}>
              {/* Distribution Pie Chart */}
              <Grid item xs={12}>
                <Card sx={{ p: 3 }}>
                  <Box sx={{ mb: 2, display: "flex", alignItems: "center", gap: 1.5 }}>
                    <PieChartRoundedIcon sx={{ color: duoColors.fox, fontSize: 28 }} />
                    <Box>
                      <Typography variant="h5" sx={{ fontWeight: 800 }}>Occupancy Distribution</Typography>
                      <Typography variant="body2" sx={{ color: duoColors.wolf }}>Time distribution of seats status</Typography>
                    </Box>
                  </Box>

                  <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", position: "relative", height: 160 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={pieData}
                          cx="50%"
                          cy="50%"
                          innerRadius={50}
                          outerRadius={70}
                          paddingAngle={5}
                          dataKey="value"
                        >
                          {pieData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                    <Box sx={{ position: "absolute", textAlign: "center" }}>
                      <Typography variant="h4" sx={{ fontWeight: 900, color: duoColors.eel }}>
                        {data.distribution.occupied_pct}%
                      </Typography>
                      <Typography variant="caption" sx={{ color: duoColors.wolf, fontWeight: 700 }}>Occupied Ratio</Typography>
                    </Box>
                  </Box>

                  {/* Custom Legend */}
                  <Box sx={{ display: "flex", justifyContent: "center", gap: 3, mt: 1 }}>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                      <Box sx={{ width: 12, height: 12, borderRadius: "50%", bgcolor: duoColors.fox }} />
                      <Typography variant="body2" sx={{ fontWeight: 700 }}>Occupied ({data.distribution.occupied_pct}%)</Typography>
                    </Box>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                      <Box sx={{ width: 12, height: 12, borderRadius: "50%", bgcolor: duoColors.featherGreen }} />
                      <Typography variant="body2" sx={{ fontWeight: 700 }}>Vacant ({data.distribution.vacant_pct}%)</Typography>
                    </Box>
                  </Box>
                </Card>
              </Grid>

              {/* Peak Utilization Metrics */}
              <Grid item xs={12}>
                <Card sx={{ p: 3, height: "calc(100% - 16px)", borderColor: duoColors.bee, borderBottomColor: duoColors.beeDark, borderBottomWidth: 4 }}>
                  <Box sx={{ mb: 2, display: "flex", alignItems: "center", gap: 1.5 }}>
                    <CalendarMonthRoundedIcon sx={{ color: duoColors.bee, fontSize: 28 }} />
                    <Box>
                      <Typography variant="h5" sx={{ fontWeight: 800 }}>Peak Utilization</Typography>
                      <Typography variant="body2" sx={{ color: duoColors.wolf }}>Highest utilization limits reached</Typography>
                    </Box>
                  </Box>

                  <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 2 }}>
                    <Box sx={{ display: "flex", justifyContent: "space-between", borderBottom: `2px solid ${duoColors.polar}`, pb: 1 }}>
                      <Typography sx={{ fontWeight: 700, color: duoColors.wolf }}>Peak Timestamp</Typography>
                      <Typography sx={{ fontWeight: 800, color: duoColors.eel }}>{formatFullDateTime(data.peak.peak_timestamp)}</Typography>
                    </Box>
                    <Box sx={{ display: "flex", justifyContent: "space-between", borderBottom: `2px solid ${duoColors.polar}`, pb: 1 }}>
                      <Typography sx={{ fontWeight: 700, color: duoColors.wolf }}>Highest Occupancy %</Typography>
                      <Typography sx={{ fontWeight: 800, color: duoColors.foxDark }}>{data.peak.highest_occupancy_pct}%</Typography>
                    </Box>
                    <Box sx={{ display: "flex", justifyContent: "space-between", borderBottom: `2px solid ${duoColors.polar}`, pb: 1 }}>
                      <Typography sx={{ fontWeight: 700, color: duoColors.wolf }}>Lowest Occupancy %</Typography>
                      <Typography sx={{ fontWeight: 800, color: duoColors.wolfDark }}>{data.peak.lowest_occupancy_pct}%</Typography>
                    </Box>
                    <Box sx={{ display: "flex", justifyContent: "space-between", pb: 1 }}>
                      <Typography sx={{ fontWeight: 700, color: duoColors.wolf }}>Average Occupancy</Typography>
                      <Typography sx={{ fontWeight: 800, color: duoColors.dodgerBlueDark }}>{data.peak.avg_occupancy_pct}%</Typography>
                    </Box>
                  </Box>
                </Card>
              </Grid>
            </Grid>
          </Grid>

          {/* ==========================================
              SECTION 3: SEAT UTILIZATION BAR CHART
             ========================================== */}
          <Grid item xs={12}>
            <Card sx={{ p: 3 }}>
              <Box sx={{ mb: 3, display: "flex", alignItems: "center", gap: 1.5 }}>
                <BarChartRoundedIcon sx={{ color: duoColors.beetle, fontSize: 28 }} />
                <Box>
                  <Typography variant="h5" sx={{ fontWeight: 800 }}>Seat Utilization</Typography>
                  <Typography variant="body2" sx={{ color: duoColors.wolf }}>Comparison of occupancy utilization across individual seats</Typography>
                </Box>
              </Box>

              {!hasSeatData ? (
                <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: 260 }}>
                  <Typography sx={{ color: duoColors.wolf, fontWeight: 700 }}>No seat data available</Typography>
                </Box>
              ) : (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={data.seat_utilization} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={duoColors.swan} vertical={false} />
                    <XAxis
                      dataKey="seat_label"
                      stroke={duoColors.wolf}
                      tick={{ fontFamily: "Nunito", fontWeight: 700, fontSize: "0.7rem" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      stroke={duoColors.wolf}
                      tick={{ fontFamily: "Nunito", fontWeight: 700, fontSize: "0.75rem" }}
                      domain={[0, 100]}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip cursor={{ fill: duoColors.polar }} content={<ChartTooltip suffix="%" />} />
                    <Bar
                      name="Utilization Rate"
                      dataKey="utilization_pct"
                      fill={duoColors.beetle}
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Card>
          </Grid>

          {/* ==========================================
              SECTION 6: SEAT-WISE STATISTICS TABLE
             ========================================== */}
          <Grid item xs={12} lg={8}>
            <Card sx={{ p: 3, height: "100%" }}>
              <Box sx={{ mb: 3, display: "flex", alignItems: "center", gap: 1.5 }}>
                <TableRowsRoundedIcon sx={{ color: duoColors.wolf, fontSize: 28 }} />
                <Box>
                  <Typography variant="h5" sx={{ fontWeight: 800 }}>Seat-wise Statistics</Typography>
                  <Typography variant="body2" sx={{ color: duoColors.wolf }}>Raw metrics break-down per physical seat</Typography>
                </Box>
              </Box>

              {!hasSeatData ? (
                <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: 280 }}>
                  <Typography sx={{ color: duoColors.wolf, fontWeight: 700 }}>No statistics available</Typography>
                </Box>
              ) : (
                <TableContainer component={Paper} elevation={0} sx={{ border: `2px solid ${duoColors.polar}`, borderRadius: 3, maxHeight: 400 }}>
                  <Table stickyHeader size="small">
                    <TableHead>
                      <TableRow sx={{ "& th": { fontWeight: 800, fontFamily: "Nunito", color: duoColors.eel, bgcolor: duoColors.polar } }}>
                        <TableCell>Seat</TableCell>
                        <TableCell>Occupied Duration</TableCell>
                        <TableCell>Vacant Duration</TableCell>
                        <TableCell align="right">Utilization %</TableCell>
                        <TableCell align="right">Occupancy Count</TableCell>
                        <TableCell align="center">Current Status</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {data.seat_stats.map((seat, index) => {
                        const isOccupied = seat.current_status === "OCCUPIED";
                        const isVacant = seat.current_status === "VACANT";
                        
                        return (
                          <TableRow key={index} sx={{ "& td": { fontFamily: "Nunito", fontWeight: 700 } }}>
                            <TableCell sx={{ color: duoColors.eel }}>{seat.seat_label}</TableCell>
                            <TableCell sx={{ color: duoColors.foxDark }}>{formatDuration(seat.occupied_duration_s)}</TableCell>
                            <TableCell sx={{ color: duoColors.featherGreenDark }}>{formatDuration(seat.vacant_duration_s)}</TableCell>
                            <TableCell align="right" sx={{ color: duoColors.beetleDark }}>{seat.utilization_pct}%</TableCell>
                            <TableCell align="right" sx={{ color: duoColors.wolf }}>{seat.occupancy_count}</TableCell>
                            <TableCell align="center">
                              <Chip
                                size="small"
                                label={seat.current_status}
                                sx={{
                                  fontWeight: 800,
                                  fontSize: "0.7rem",
                                  borderRadius: 2,
                                  bgcolor: isOccupied
                                    ? "#FCE8E6"
                                    : isVacant
                                    ? "#E6F9D4"
                                    : duoColors.polar,
                                  color: isOccupied
                                    ? duoColors.foxDark
                                    : isVacant
                                    ? duoColors.featherGreenDark
                                    : duoColors.wolf,
                                  border: `2px solid ${
                                    isOccupied
                                      ? duoColors.fox
                                      : isVacant
                                      ? duoColors.featherGreen
                                      : duoColors.swan
                                  }`,
                                }}
                              />
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Card>
          </Grid>

          {/* ==========================================
              SECTION 7: PERFORMANCE METRICS
             ========================================== */}
          <Grid item xs={12} lg={4}>
            <Card sx={{ p: 3, height: "100%", borderColor: duoColors.wolf, borderBottomColor: duoColors.wolfDark, borderBottomWidth: 4 }}>
              <Box sx={{ mb: 3, display: "flex", alignItems: "center", gap: 1.5 }}>
                <SettingsSuggestRoundedIcon sx={{ color: duoColors.wolf, fontSize: 28 }} />
                <Box>
                  <Typography variant="h5" sx={{ fontWeight: 800 }}>Performance Metrics</Typography>
                  <Typography variant="body2" sx={{ color: duoColors.wolf }}>Computer vision pipeline monitoring stats</Typography>
                </Box>
              </Box>

              <Box sx={{ display: "flex", flexDirection: "column", gap: 2.5, mt: 1 }}>
                <Card variant="outlined" sx={{ p: 2, borderRadius: 3, bgcolor: duoColors.polar }}>
                  <Typography variant="caption" sx={{ color: duoColors.wolf, fontWeight: 700 }}>Processing FPS</Typography>
                  <Typography variant="h4" sx={{ color: duoColors.eel, mt: 0.5, fontWeight: 900 }}>
                    {data.performance.fps ? `${data.performance.fps.toFixed(1)} fps` : "0.0 fps"}
                  </Typography>
                </Card>

                <Card variant="outlined" sx={{ p: 2, borderRadius: 3, bgcolor: duoColors.polar }}>
                  <Typography variant="caption" sx={{ color: duoColors.wolf, fontWeight: 700 }}>Frames Processed</Typography>
                  <Typography variant="h4" sx={{ color: duoColors.eel, mt: 0.5, fontWeight: 900 }}>
                    {data.performance.frames_processed}
                  </Typography>
                </Card>

                <Card variant="outlined" sx={{ p: 2, borderRadius: 3, bgcolor: duoColors.polar }}>
                  <Typography variant="caption" sx={{ color: duoColors.wolf, fontWeight: 700 }}>Average Processing Time</Typography>
                  <Typography variant="h4" sx={{ color: duoColors.eel, mt: 0.5, fontWeight: 900 }}>
                    {data.performance.avg_processing_time ? `${data.performance.avg_processing_time.toFixed(1)} ms` : "0.0 ms"}
                  </Typography>
                </Card>

                <Card variant="outlined" sx={{ p: 2, borderRadius: 3, bgcolor: duoColors.polar }}>
                  <Typography variant="caption" sx={{ color: duoColors.wolf, fontWeight: 700 }}>Total Video Length / Analysis Duration</Typography>
                  <Typography variant="h5" sx={{ color: duoColors.eel, mt: 0.5, fontWeight: 900 }}>
                    {formatDuration(data.performance.total_video_length)} / {formatDuration(data.performance.analysis_duration)}
                  </Typography>
                </Card>
              </Box>
            </Card>
          </Grid>

        </Grid>
      )}
    </Box>
  );
}
