/**
 * Analytics — what has happened in the workspace over time.
 * Every number is measured from stored state changes (time-weighted).
 */

import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/endpoints";
import { useWorkspace } from "../lib/workspace";
import { useAsync } from "../lib/useAsync";
import { downloadCsv } from "../lib/csv";
import { clock, compareLabels, dateTime, duration, num, pct, spanWords, statusLabel } from "../lib/format";
import { HourlyBars, Heatmap, TimeArea } from "../components/data/charts";
import { CountUp, Reveal, WhenVisible } from "../components/motion";
import { DemoBadge, Segmented, Stat, StatusDot, Toggle, UtilBar } from "../components/ui";
import { EmptyState, ErrorState, Skeleton } from "../components/feedback";
import SeatDrawer from "../features/seats/SeatDrawer";
import Icon from "../components/ui/Icon";
import "./pages.css";

const RANGES = [
  { value: 1, label: "1 h" },
  { value: 6, label: "6 h" },
  { value: 24, label: "24 h" },
  { value: 168, label: "7 days" },
];

function SortableTable({ rows, columns, initial, onRow, cap = 25 }) {
  const [sort, setSort] = useState(initial);
  const [all, setAll] = useState(false);
  const sorted = useMemo(() => {
    const col = columns.find((c) => c.key === sort.key);
    const get = col?.sort || ((r) => r[sort.key]);
    return [...rows].sort((a, b) => {
      const av = get(a);
      const bv = get(b);
      if (typeof av === "string" || typeof bv === "string") return compareLabels(av ?? "", bv ?? "") * sort.dir;
      return ((av ?? -1) - (bv ?? -1)) * sort.dir;
    });
  }, [rows, sort, columns]);
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} aria-sort={sort.key === c.key ? (sort.dir > 0 ? "ascending" : "descending") : "none"}>
                <button type="button" onClick={() => setSort((s) => ({ key: c.key, dir: s.key === c.key ? -s.dir : c.numeric ? -1 : 1 }))}>
                  {c.label}
                  {sort.key === c.key ? (sort.dir > 0 ? " ↑" : " ↓") : ""}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(all ? sorted : sorted.slice(0, cap)).map((r, i) => (
            <tr key={r.seat_id || r.startup_id || r.id || i} data-clickable={onRow ? "true" : undefined} onClick={onRow ? () => onRow(r) : undefined}>
              {columns.map((c) => (
                <td key={c.key} className={c.className}>
                  {c.render ? c.render(r) : r[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {sorted.length > cap && (
        <div style={{ padding: "12px 16px", borderTop: "1px solid var(--line)" }}>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAll((v) => !v)}>
            {all ? `Show first ${cap}` : `Show all ${sorted.length}`}
          </button>
        </div>
      )}
    </div>
  );
}

export default function Analytics() {
  const ws = useWorkspace();
  const [range, setRange] = useState(24);
  const [selected, setSelected] = useState(null);
  const { data, error, loading, reload } = useAsync(
    () => api.analytics(ws.buildingId, { range_hours: range, include_demo: ws.includeDemo }),
    [ws.buildingId, range, ws.includeDemo],
    { enabled: !!ws.buildingId }
  );
  const sessions = useAsync(() => api.sessions({ limit: 12 }), []);

  const timeFmt = range > 24 ? (t) => dateTime(t) : (t) => clock(t);

  const seatColumns = [
    { key: "seat_label", label: "Seat", className: "mono" },
    { key: "zone", label: "Zone", className: "muted" },
    { key: "startup_name", label: "Team", render: (r) => r.startup_name || <span className="muted">Unassigned</span> },
    {
      key: "current_status",
      label: "Now",
      render: (r) => (
        <span className="row" style={{ gap: 6 }}>
          <StatusDot status={r.current_status} /> {statusLabel[r.current_status]}
        </span>
      ),
    },
    { key: "utilization_pct", label: "Utilization", numeric: true, render: (r) => <UtilBar value={r.utilization_pct} /> },
    { key: "occupied_duration_s", label: "Occupied", numeric: true, render: (r) => duration(r.occupied_duration_s) },
    { key: "vacant_duration_s", label: "Vacant", numeric: true, render: (r) => duration(r.vacant_duration_s) },
    { key: "sessions", label: "Sessions", numeric: true },
    { key: "avg_session_s", label: "Average session", numeric: true, render: (r) => duration(r.avg_session_s) },
    { key: "longest_session_s", label: "Longest", numeric: true, render: (r) => duration(r.longest_session_s) },
  ];

  const exportCsv = () => {
    downloadCsv(`seat-utilization-${range}h.csv`, [
      { label: "Seat", value: "seat_label" },
      { label: "Zone", value: "zone" },
      { label: "Floor", value: "floor" },
      { label: "Team", value: "startup_name" },
      { label: "Current status", value: "current_status" },
      { label: "Utilization %", value: "utilization_pct" },
      { label: "Occupied seconds", value: "occupied_duration_s" },
      { label: "Vacant seconds", value: "vacant_duration_s" },
      { label: "Observed seconds", value: "observed_duration_s" },
      { label: "Sessions", value: "sessions" },
      { label: "Average session seconds", value: "avg_session_s" },
      { label: "Longest session seconds", value: "longest_session_s" },
      { label: "First occupied", value: "first_occupied" },
      { label: "Last occupied", value: "last_occupied" },
    ], data.seat_stats);
  };

  const k = data?.kpi;
  const hasObs = k && k.observed_seat_hours > 0;
  const peakWin = data?.peak?.window;

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Analytics</h1>
          <p className="page-lede">Measured from every seat change the system recorded: time occupied, time vacant, and how that shifts across the day.</p>
        </div>
        <div className="page-actions">
          {data?.sources.include_demo && data?.sources.demo_available && <DemoBadge />}
          {(ws.demoDataPresent || ws.demoMode) && (
            <Toggle checked={ws.includeDemo} onChange={ws.setIncludeDemo}>
              Demo data
            </Toggle>
          )}
          <Segmented id="range" label="Time range" options={RANGES} value={range} onChange={setRange} />
          <button type="button" className="btn btn-sm" onClick={exportCsv} disabled={!data?.seat_stats?.length}>
            <Icon name="download" /> Export CSV
          </button>
        </div>
      </header>

      {error && <ErrorState error={error} onRetry={reload} title="Unable to retrieve occupancy data" />}
      {!data && !error && (
        <div style={{ display: "grid", gap: 16 }}>
          <Skeleton height={90} />
          <Skeleton height={280} />
        </div>
      )}

      {data && !hasObs && (
        <EmptyState
          title="Not enough data in this range yet"
          action={
            <Link to="/" className="btn btn-sm">
              <Icon name="upload" /> Analyze a video
            </Link>
          }
        >
          Analytics are built from processed videos. Run an analysis, or widen the time range.
          {ws.demoDataPresent && !ws.includeDemo && " You can also switch on demo data to explore the seeded example workspace."}
        </EmptyState>
      )}

      {data && hasObs && (
        <div style={{ opacity: loading ? 0.6 : 1, transition: "opacity 200ms" }}>
          <Reveal className="stat-row">
            <Stat label="Average occupancy" value={<CountUp value={k.avg_occupancy_pct} format={(v) => pct(v, 1)} />} note="Share of observed seat-time occupied" />
            <Stat
              label="Peak occupancy"
              value={pct(k.max_occupancy_pct)}
              note={data.peak.peak_seats ? `${data.peak.peak_seats} seats at once, first at ${timeFmt(data.peak.peak_seats_at)}` : undefined}
            />
            <Stat label="Lowest occupancy" value={pct(k.min_occupancy_pct)} />
            <Stat label="Observed" value={<>{num(k.observed_seat_hours, 1)}<small>seat-h</small></>} note={`${num(k.occupied_seat_hours, 1)} seat-hours occupied`} />
            <Stat label="Unused capacity" value={pct(data.capacity.unused_capacity_pct)} note="Observed seat-time left vacant" />
          </Reveal>

          <section className="section panel">
            <div className="chart-panel-head">
              <div>
                <h2 className="panel-title">Occupancy over time</h2>
                <div className="panel-sub">
                  Occupied share of observed seats in {spanWords(data.window.bucket_s).replace(/^(\d+) /, "$1-").replace(/s$/, "")} steps. Gaps mean no camera was running.
                </div>
              </div>
              {peakWin && (
                <span className="badge badge-occupied">
                  Peak period {timeFmt(peakWin.start)}–{timeFmt(peakWin.end)}
                </span>
              )}
            </div>
            <WhenVisible minHeight={280}>
              <TimeArea
                id="occ"
                data={data.timeline}
                xKey="time"
                yKey="occupancy_pct"
                height={280}
                xFormat={timeFmt}
                highlight={
                  peakWin
                    ? {
                        x1: data.timeline.find((t) => t.time >= peakWin.start)?.time,
                        x2: [...data.timeline].reverse().find((t) => t.time < peakWin.end)?.time,
                      }
                    : null
                }
              />
            </WhenVisible>
          </section>

          <div className="grid-12 section">
            <section className="col-7 panel">
              <div className="chart-panel-head">
                <div>
                  <h2 className="panel-title">By hour of day</h2>
                  <div className="panel-sub">Average occupancy in each hour, your local time. The busiest hour is in red.</div>
                </div>
              </div>
              <WhenVisible minHeight={220}>
                <HourlyBars hourly={data.hourly} />
              </WhenVisible>
            </section>
            <section className="col-5 panel">
              <h2 className="panel-title">Capacity</h2>
              <div className="panel-sub" style={{ marginBottom: 16 }}>
                {data.capacity.total_capacity} seats tracked in this range
              </div>
              <dl className="seat-stats" style={{ gridTemplateColumns: "1fr 1fr" }}>
                <div>
                  <dt>Average utilization</dt>
                  <dd>{pct(data.capacity.avg_utilization_pct, 1)}</dd>
                </div>
                <div>
                  <dt>Peak utilization</dt>
                  <dd>{pct(data.capacity.peak_utilization_pct)}</dd>
                </div>
              </dl>
              <div style={{ marginTop: 16 }}>
                <div className="small">
                  Under-used <span className="faint">(below 20%)</span>
                </div>
                <div className="cap-list">
                  {data.capacity.under_utilized_seats.length ? (
                    data.capacity.under_utilized_seats.slice(0, 24).map((l) => (
                      <span key={l} className="badge">
                        {l}
                      </span>
                    ))
                  ) : (
                    <span className="xs faint">None</span>
                  )}
                </div>
              </div>
              <div style={{ marginTop: 16 }}>
                <div className="small">
                  Over-used <span className="faint">(above 85%)</span>
                </div>
                <div className="cap-list">
                  {data.capacity.over_utilized_seats.length ? (
                    data.capacity.over_utilized_seats.slice(0, 24).map((l) => (
                      <span key={l} className="badge badge-occupied">
                        {l}
                      </span>
                    ))
                  ) : (
                    <span className="xs faint">None</span>
                  )}
                </div>
              </div>
            </section>
          </div>

          <section className="section">
            <div className="section-head">
              <div>
                <h2 className="section-title">Seat utilization by hour</h2>
                <p className="section-sub">Each cell is the share of that hour a seat was occupied. Hatched cells were not observed.</p>
              </div>
            </div>
            <div className="panel">
              <WhenVisible minHeight={160}>
                <Heatmap heatmap={data.heatmap} onSelect={(s) => setSelected(s.seat_id)} />
              </WhenVisible>
            </div>
          </section>

          <section className="section">
            <div className="section-head">
              <div>
                <h2 className="section-title">Seats</h2>
                <p className="section-sub">Select a seat for its full history. Sort by any column.</p>
              </div>
            </div>
            <SortableTable rows={data.seat_stats} columns={seatColumns} initial={{ key: "seat_label", dir: 1 }} onRow={(r) => setSelected(r.seat_id)} />
          </section>

          <section className="section">
            <div className="section-head">
              <div>
                <h2 className="section-title">Teams</h2>
                <p className="section-sub">Measured against the seats each team is assigned. Assign seats from the explorer.</p>
              </div>
            </div>
            {data.startup_stats.length ? (
              <SortableTable
                rows={data.startup_stats}
                initial={{ key: "name", dir: 1 }}
                columns={[
                  { key: "name", label: "Team" },
                  { key: "assigned_seats", label: "Assigned seats", numeric: true },
                  { key: "contracted_seats", label: "Contracted", numeric: true, render: (r) => r.contracted_seats ?? "—" },
                  { key: "occupied_now", label: "Occupied now", numeric: true },
                  { key: "unused_now", label: "Unused now", numeric: true, render: (r) => r.unused_now ?? "—" },
                  { key: "peak_concurrent", label: "Peak at once", numeric: true },
                  { key: "utilization_pct", label: "Utilization", numeric: true, render: (r) => <UtilBar value={r.utilization_pct} /> },
                  {
                    key: "status",
                    label: "Status",
                    render: (r) =>
                      r.status === "UNDER_UTILIZED" ? (
                        <span className="badge badge-warn">Under-used</span>
                      ) : r.status === "AT_CAPACITY" ? (
                        <span className="badge badge-occupied">At capacity</span>
                      ) : r.status === "BALANCED" ? (
                        <span className="badge">Balanced</span>
                      ) : (
                        <span className="muted">—</span>
                      ),
                  },
                ]}
              />
            ) : (
              <EmptyState title="No seats are assigned to teams">
                Open a seat in the explorer or on the live page and choose a team. Team utilization appears here once assigned seats have been observed.
              </EmptyState>
            )}
          </section>

          <section className="section grid-12">
            <div className="col-8">
              <div className="section-head">
                <div>
                  <h2 className="section-title">Analysis sessions</h2>
                  <p className="section-sub">Every processed video, newest first.</p>
                </div>
              </div>
              {sessions.data?.length ? (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Video</th>
                        <th>Processed</th>
                        <th>Status</th>
                        <th>Seats</th>
                        <th>Peak</th>
                        <th>Average</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sessions.data.map((s) => (
                        <tr key={s.id}>
                          <td>
                            <Link to={`/sessions/${s.id}`} className="row" style={{ gap: 8 }}>
                              <Icon name="film" size={16} />
                              {s.source_filename || "video"}
                            </Link>
                          </td>
                          <td className="muted">{dateTime(s.created_at)}</td>
                          <td>{s.status.charAt(0) + s.status.slice(1).toLowerCase()}</td>
                          <td>{s.seat_count}</td>
                          <td>{s.peak_occupied ?? "—"}</td>
                          <td>{pct(s.avg_occupancy_pct, 1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyState title="No videos analysed yet" />
              )}
            </div>
            <div className="col-4">
              <div className="section-head">
                <div>
                  <h2 className="section-title">Pipeline performance</h2>
                  <p className="section-sub">{data.performance.source === "live" ? "Current run" : data.performance.source ? "Most recent run" : "No runs yet"}</p>
                </div>
              </div>
              <dl className="seat-stats panel" style={{ gridTemplateColumns: "1fr 1fr", padding: "0 20px" }}>
                <div>
                  <dt>Checks per second</dt>
                  <dd>{num(data.performance.fps, 1)}</dd>
                </div>
                <div>
                  <dt>Time per check</dt>
                  <dd>{data.performance.avg_processing_time ? `${num(data.performance.avg_processing_time)} ms` : "—"}</dd>
                </div>
                <div>
                  <dt>Frames processed</dt>
                  <dd>{num(data.performance.frames_processed)}</dd>
                </div>
                <div>
                  <dt>Video length</dt>
                  <dd>{duration(data.performance.total_video_length)}</dd>
                </div>
              </dl>
            </div>
          </section>
        </div>
      )}

      <SeatDrawer seatId={selected} onClose={() => setSelected(null)} onChanged={reload} />
    </div>
  );
}
