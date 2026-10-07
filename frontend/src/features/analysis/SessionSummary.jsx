/**
 * Post-analysis summary for one processed video. All figures are measured in
 * video time from the transitions the pipeline observed.
 */

import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { duration, num, pct, videoTime, compareLabels } from "../../lib/format";
import { TimeArea } from "../../components/data/charts";
import { WhenVisible, Reveal } from "../../components/motion";
import { UtilBar } from "../../components/ui";
import "./analysis.css";

function Fact({ label, children, note }) {
  return (
    <div className="fact">
      <dt>{label}</dt>
      <dd>{children}</dd>
      {note && <div className="xs faint">{note}</div>}
    </div>
  );
}

export function SummaryFacts({ summary }) {
  const w = summary.peak_window;
  return (
    <dl className="facts">
      <Fact label="Seats detected">{summary.seat_count}</Fact>
      <Fact label="Peak occupancy" note={summary.peak_at_s !== null ? `at ${videoTime(summary.peak_at_s)}` : "no seat was occupied"}>
        {summary.peak_occupied}
        <small>of {summary.seat_count}</small>
      </Fact>
      <Fact label="Average occupancy">{pct(summary.avg_occupancy_pct, 1)}</Fact>
      <Fact label="Occupied seat-time">{duration(summary.total_occupied_s)}</Fact>
      <Fact label="Most used seat" note={summary.most_utilized ? pct(summary.most_utilized.utilization_pct) : undefined}>
        {summary.most_utilized?.label || "—"}
      </Fact>
      <Fact label="Least used seat" note={summary.least_utilized ? pct(summary.least_utilized.utilization_pct) : undefined}>
        {summary.least_utilized?.label || "—"}
      </Fact>
      <Fact label="Peak period">{w ? `${videoTime(w.start)}–${videoTime(w.end)}` : "—"}</Fact>
      <Fact label="Seat changes">{summary.state_changes}</Fact>
    </dl>
  );
}

export function SummaryTimeline({ summary, height = 220 }) {
  const data = summary.timeline || [];
  const max = Math.max(1, summary.seat_count || 1);
  if (!data.length) return null;
  const w = summary.peak_window;
  return (
    <WhenVisible minHeight={height}>
      <TimeArea
        id="session"
        data={data}
        xKey="t"
        yKey="occupied"
        height={height}
        yDomain={[0, max]}
        yFormat={(v) => num(v, v % 1 ? 1 : 0)}
        xFormat={(t) => videoTime(t)}
        yLabel="Seats occupied"
        highlight={w ? { x1: data.find((d) => d.t >= w.start)?.t, x2: [...data].reverse().find((d) => d.t < w.end)?.t } : null}
        color="var(--occupied)"
      />
    </WhenVisible>
  );
}

export function SummarySeats({ summary, onSelect }) {
  const [sort, setSort] = useState({ key: "label", dir: 1 });
  const rows = useMemo(() => {
    const r = [...(summary.seats || [])];
    r.sort((a, b) => {
      const av = a[sort.key];
      const bv = b[sort.key];
      if (sort.key === "label") return compareLabels(av, bv) * sort.dir;
      return ((av ?? -1) - (bv ?? -1)) * sort.dir;
    });
    return r;
  }, [summary, sort]);

  const th = (key, label) => (
    <th aria-sort={sort.key === key ? (sort.dir > 0 ? "ascending" : "descending") : "none"}>
      <button type="button" onClick={() => setSort((s) => ({ key, dir: s.key === key ? -s.dir : key === "label" ? 1 : -1 }))}>
        {label}
        {sort.key === key ? (sort.dir > 0 ? " ↑" : " ↓") : ""}
      </button>
    </th>
  );

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            {th("label", "Seat")}
            {th("utilization_pct", "Utilization")}
            {th("occupied_s", "Occupied")}
            {th("vacant_s", "Vacant")}
            {th("sessions", "Sessions")}
            {th("avg_session_s", "Average session")}
            {th("longest_session_s", "Longest")}
            {th("first_occupied", "First occupied")}
            {th("last_occupied", "Last occupied")}
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.seat_id} data-clickable={onSelect ? "true" : undefined} onClick={onSelect ? () => onSelect(s) : undefined}>
              <td className="mono">{s.label}</td>
              <td>
                <UtilBar value={s.utilization_pct} />
              </td>
              <td>{duration(s.occupied_s)}</td>
              <td>{duration(s.vacant_s)}</td>
              <td>{s.sessions}</td>
              <td>{duration(s.avg_session_s)}</td>
              <td>{duration(s.longest_session_s)}</td>
              <td className="mono">{videoTime(s.first_occupied)}</td>
              <td className="mono">{videoTime(s.last_occupied)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Diagnostics({ summary }) {
  const c = summary.calibration || {};
  const p = summary.performance || {};
  const items = [
    ["Calibration frames scanned", num(c.frames_scanned)],
    ["Frames sampled", num(c.frames_sampled)],
    ["Person-free frames", num(c.person_free_frames)],
    ["Detection pool", c.pool === "clean" ? "Person-free frames" : c.pool === "combined" ? "All frames" : "—"],
    ["Raw chair detections", num(c.raw_detections)],
    ["Rejected by size/shape", num(c.geometry_rejected)],
    ["Persistent clusters", num(c.persistent_clusters)],
    ["Vetoed as screens", num(c.static_vetoed)],
    ["Merged duplicates", num(c.nms_suppressed)],
    ["Frames processed", num(p.frames_processed)],
    ["Occupancy checks", num(p.frames_inferred)],
    ["Checks per second", num(p.inference_fps, 1)],
    ["Average time per check", p.avg_inference_ms ? `${num(p.avg_inference_ms)} ms` : "—"],
    ["Processing time", duration(p.processing_s)],
  ];
  return (
    <dl className="diag">
      {items.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd className="num">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function SessionSummary({ summary, session, status, compact = false }) {
  if (!summary) return null;
  const stopped = status === "STOPPED";
  return (
    <div>
      <div className="summary-head">
        <div>
          <h2 className="summary-title">{stopped ? "Analysis stopped" : "Analysis complete"}</h2>
          <p className="muted small">
            {session?.source_filename || "Video"}, {videoTime(summary.duration_s)} analysed
            {stopped ? ". Figures cover the part that was processed." : "."}
          </p>
        </div>
        {compact && session?.id && (
          <Link to={`/sessions/${session.id}`} className="btn btn-sm">
            Open full summary
          </Link>
        )}
      </div>
      <Reveal>
        <SummaryFacts summary={summary} />
      </Reveal>
      <div style={{ marginTop: 24 }}>
        <div className="panel-sub" style={{ marginBottom: 8 }}>
          Seats occupied over the video
        </div>
        <SummaryTimeline summary={summary} height={compact ? 180 : 240} />
      </div>
    </div>
  );
}
