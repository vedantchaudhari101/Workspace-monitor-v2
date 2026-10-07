/**
 * Live — what is happening in the workspace right now.
 */

import { useEffect, useMemo, useState } from "react";
import { api } from "../api/endpoints";
import { useWorkspace } from "../lib/workspace";
import { useAsync, useInterval } from "../lib/useAsync";
import { hydrateCamera, useCamera } from "../lib/live/store";
import { compareLabels, num, pct, videoTime } from "../lib/format";
import { apiUrl } from "../api/client";
import AnalysisConsole from "../features/analysis/AnalysisConsole";
import SessionSummary from "../features/analysis/SessionSummary";
import ActivityFeed from "../features/activity/ActivityFeed";
import SeatDrawer from "../features/seats/SeatDrawer";
import SeatMap from "../components/data/SeatMap";
import SeatGrid from "../components/data/SeatGrid";
import { TimeArea } from "../components/data/charts";
import { CountUp, Reveal } from "../components/motion";
import { DemoBadge, Segmented, Stat, StatusDot } from "../components/ui";
import { EmptyState, ErrorState, Skeleton } from "../components/feedback";
import Icon from "../components/ui/Icon";
import "./pages.css";

const FILTERS = [
  { value: "all", label: "All" },
  { value: "OCCUPIED", label: "Occupied" },
  { value: "VACANT", label: "Available" },
];

export default function Live() {
  const ws = useWorkspace();
  const cam = useCamera(ws.cameraId);
  const [view, setView] = useState("map");
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState(null);

  // Seed the live store from REST so a refresh mid-analysis restores state.
  const state = useAsync(() => (ws.cameraId ? api.cameraState(ws.cameraId) : null), [ws.cameraId], { enabled: !!ws.cameraId });
  useEffect(() => {
    if (state.data) hydrateCamera(state.data);
  }, [state.data]);

  const analytics = useAsync(
    () => api.analytics(ws.buildingId, { range_hours: 24, include_demo: ws.includeDemo }),
    [ws.buildingId, ws.includeDemo],
    { enabled: !!ws.buildingId }
  );
  const activity = useAsync(
    () => api.activity(ws.buildingId, { limit: 20, include_demo: ws.includeDemo }),
    [ws.buildingId, ws.includeDemo],
    { enabled: !!ws.buildingId }
  );
  const lastSession = useAsync(
    () => api.sessions({ camera_id: ws.cameraId, limit: 1 }),
    [ws.cameraId, cam.status === "COMPLETED"],
    { enabled: !!ws.cameraId }
  );

  const running = ["PROCESSING", "ANALYZING", "SIMULATING"].includes(cam.status);
  useInterval(() => {
    analytics.reload();
    activity.reload();
  }, running ? 15000 : 60000);

  // Refresh stored data once a run finishes.
  useEffect(() => {
    if (["COMPLETED", "STOPPED"].includes(cam.status)) {
      analytics.reload();
      activity.reload();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cam.status]);

  const seatMeta = useMemo(() => {
    const m = {};
    for (const r of analytics.data?.seat_stats || []) m[r.seat_id] = r;
    return m;
  }, [analytics.data]);

  const liveSeats = useMemo(
    () =>
      [...cam.seats]
        .map((s) => ({ ...s, startup_name: seatMeta[s.seat_id]?.startup_name, utilization_pct: seatMeta[s.seat_id]?.utilization_pct }))
        .sort((a, b) => compareLabels(a.label, b.label)),
    [cam.seats, seatMeta]
  );

  const hasLive = liveSeats.length > 0;
  const occupied = liveSeats.filter((s) => cam.statusById[s.seat_id] === "OCCUPIED").length;
  const total = hasLive ? liveSeats.length : analytics.data?.kpi.total_seats ?? 0;
  const activeTeams = new Set(liveSeats.filter((s) => cam.statusById[s.seat_id] === "OCCUPIED" && s.startup_name).map((s) => s.startup_name)).size;
  const filtered = filter === "all" ? liveSeats : liveSeats.filter((s) => cam.statusById[s.seat_id] === filter);

  const finishedSummary = cam.summary;
  const sessionMeta = lastSession.data?.[0];

  if (ws.error) return <div className="page"><ErrorState error={ws.error} onRetry={ws.reload} title="Couldn't load the workspace" /></div>;
  if (!ws.ready) {
    return (
      <div className="page">
        <Skeleton height={48} width="40%" />
        <Skeleton height={420} style={{ marginTop: 24 }} />
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Live workspace</h1>
          <p className="page-lede">
            {ws.building?.name}. Upload footage from a fixed camera and every seat is tracked as the video plays.
          </p>
        </div>
        <div className="page-actions">
          {cam.demo && <DemoBadge title="This camera is running a simulation, not real video" />}
          {ws.cameras.length > 1 && (
            <select
              className="select select-sm"
              value={ws.cameraId || ""}
              onChange={(e) => ws.setCameraId(e.target.value)}
              aria-label="Camera"
            >
              {ws.cameras.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          )}
        </div>
      </header>

      <Reveal className="live-hero">
        <div className="live-hero-figure">
          <span className="live-hero-num num">
            {hasLive ? (
              <>
                <CountUp value={occupied} />
                <span className="live-hero-of">/ {total}</span>
              </>
            ) : (
              <>
                <CountUp value={total} />
                <span className="live-hero-of">seats</span>
              </>
            )}
          </span>
          <span className="live-hero-caption">
            {hasLive ? (
              <>
                seats occupied {running ? "right now" : `at the end of ${cam.sourceFilename || "the last video"}`}
              </>
            ) : running ? (
              "Calibrating seats from the video. Live occupancy starts as soon as the chairs are found."
            ) : (
              total
                ? "tracked in this workspace. No camera is running, so nothing is observed right now."
                : "No seats yet. Analyze a video to calibrate this camera's seats."
            )}
          </span>
        </div>
        <div className="stat-row live-hero-stats">
          <Stat label="Available" value={hasLive ? liveSeats.length - occupied : "—"} />
          <Stat label="Occupancy" value={hasLive && liveSeats.length ? pct((occupied / liveSeats.length) * 100) : "—"} />
          <Stat label="Active teams" value={hasLive ? activeTeams : "—"} note={hasLive && !activeTeams ? "Assign seats to teams in the explorer" : undefined} />
          <Stat
            label="Utilization, 24 h"
            value={analytics.data ? pct(analytics.data.kpi.avg_occupancy_pct) : "—"}
            note={analytics.data ? `${num(analytics.data.kpi.observed_seat_hours, 1)} seat-hours observed` : undefined}
          />
        </div>
      </Reveal>

      <div className="grid-12 live-main">
        <div className="col-8">
          <AnalysisConsole
            cameraId={ws.cameraId}
            cam={cam}
            maxUploadMb={ws.maxUploadMb}
            sample={ws.sample}
            onUploaded={() => lastSession.reload()}
          />
        </div>

        <aside className="col-4 panel live-seats" aria-label="Seat matrix">
          <div className="spread" style={{ marginBottom: 12 }}>
            <div>
              <h2 className="panel-title">Seats</h2>
              <div className="panel-sub">{hasLive ? `${liveSeats.length} detected by calibration` : "Waiting for calibration"}</div>
            </div>
            <div className="row">
              <button
                type="button"
                className={`btn btn-sm ${view === "map" ? "" : "btn-ghost"}`}
                onClick={() => setView("map")}
                aria-pressed={view === "map"}
                aria-label="Map view"
              >
                <Icon name="map" />
              </button>
              <button
                type="button"
                className={`btn btn-sm ${view === "grid" ? "" : "btn-ghost"}`}
                onClick={() => setView("grid")}
                aria-pressed={view === "grid"}
                aria-label="Grid view"
              >
                <Icon name="grid" />
              </button>
            </div>
          </div>

          {hasLive ? (
            <>
              <div className="spread" style={{ marginBottom: 12 }}>
                <Segmented id="live-filter" label="Filter seats" options={FILTERS} value={filter} onChange={setFilter} />
              </div>
              {view === "map" ? (
                <SeatMap
                  seats={liveSeats}
                  frameW={cam.frameW}
                  frameH={cam.frameH}
                  cameraId={ws.cameraId}
                  background={!cam.demo && cam.sessionId ? apiUrl(`/api/v1/occupancy/camera/${ws.cameraId}/snapshot?s=${cam.sessionId}`) : undefined}
                  onSelect={cam.demo ? undefined : (s) => setSelected(s.seat_id)}
                  selectedId={selected}
                  isDim={filter === "all" ? undefined : (s) => cam.statusById[s.seat_id] !== filter}
                  ariaLabel="Seats in camera view"
                />
              ) : (
                <SeatGrid seats={filtered} cameraId={ws.cameraId} onSelect={(s) => setSelected(s.seat_id)} selectedId={selected} />
              )}
              <div className="legend" style={{ marginTop: 12 }}>
                <span>
                  <StatusDot status="OCCUPIED" /> Occupied
                </span>
                <span>
                  <StatusDot status="VACANT" /> Available
                </span>
                <span>
                  <StatusDot status="UNKNOWN" /> Not observed
                </span>
              </div>
            </>
          ) : (
            <EmptyState title="No seats yet">
              Seats appear once calibration finds the chairs in your video. Select one to see its history and assign it to a team.
            </EmptyState>
          )}
        </aside>
      </div>

      <div className="grid-12 section" style={{ alignItems: "start" }}>
        <section className="col-5 panel" aria-labelledby="activity-title">
          <div className="spread" style={{ marginBottom: 8 }}>
            <h2 className="panel-title" id="activity-title">
              Current activity
            </h2>
            <span className="xs faint">Seats taken and freed</span>
          </div>
          {activity.error ? (
            <ErrorState error={activity.error} onRetry={activity.reload} />
          ) : (
            <ActivityFeed
              live={cam.transitions.map((t) => ({ ...t, startup_name: seatMeta[t.seat_id]?.startup_name }))}
              stored={activity.data || []}
              onSelect={(it) => setSelected(it.seat_id)}
            />
          )}
        </section>

        <section className="col-7 panel" aria-label="Session">
          {cam.status === "ANALYZING" && cam.timeline.length > 1 ? (
            <>
              <div className="spread" style={{ marginBottom: 8 }}>
                <h2 className="panel-title">This session so far</h2>
                <span className="xs faint mono">{videoTime(cam.videoTs)} into the video</span>
              </div>
              <TimeArea
                id="live"
                data={cam.timeline}
                xKey="t"
                yKey="occupied"
                height={240}
                yDomain={[0, Math.max(1, liveSeats.length)]}
                yFormat={(v) => num(v)}
                xFormat={(t) => videoTime(t)}
                yLabel="Seats occupied"
                color="var(--occupied)"
              />
            </>
          ) : finishedSummary ? (
            <SessionSummary summary={finishedSummary} status={cam.status} session={{ id: cam.sessionId, source_filename: cam.sourceFilename }} compact />
          ) : sessionMeta ? (
            <LastSession meta={sessionMeta} />
          ) : (
            <EmptyState title="No analysis yet">
              When a video finishes you'll get a summary here: peak occupancy, average use, the busiest and quietest seats.
            </EmptyState>
          )}
        </section>
      </div>

      <SeatDrawer seatId={selected} cameraId={ws.cameraId} onClose={() => setSelected(null)} onChanged={analytics.reload} />
    </div>
  );
}

function LastSession({ meta }) {
  const detail = useAsync(() => api.session(meta.id), [meta.id]);
  if (detail.error) return <ErrorState error={detail.error} onRetry={detail.reload} />;
  if (!detail.data) return <Skeleton height={220} />;
  if (!detail.data.summary) {
    return (
      <EmptyState title={`Last run: ${meta.source_filename || "video"}`}>
        {meta.status === "FAILED" || meta.status === "STOPPED"
          ? meta.error || "This run ended before a summary was produced."
          : "This run has no summary."}
      </EmptyState>
    );
  }
  return <SessionSummary summary={detail.data.summary} status={detail.data.status} session={detail.data} compact />;
}
