/**
 * Recommendations — what the measurements suggest doing.
 *
 * Three kinds of output are kept visibly separate:
 *   1. Measured insights — facts computed from observed occupancy.
 *   2. Rule-based recommendations — fixed rules over those facts, each showing
 *      its rule and evidence.
 *   3. The seat-allocation engine — the original rules over stored occupancy
 *      snapshots, with approve/reject that changes allocations.
 * A statistical forecast is shown when snapshot history exists. Nothing here
 * is a machine-learning model; the roadmap note says so.
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/endpoints";
import { useWorkspace } from "../lib/workspace";
import { useAsync } from "../lib/useAsync";
import { clock, dateTime, num } from "../lib/format";
import { TimeArea } from "../components/data/charts";
import { Reveal, WhenVisible } from "../components/motion";
import { DemoBadge, Segmented } from "../components/ui";
import { EmptyState, ErrorState, Skeleton } from "../components/feedback";
import Icon from "../components/ui/Icon";
import "./pages.css";

const RANGES = [
  { value: 24, label: "24 h" },
  { value: 168, label: "7 days" },
];

function Lane({ title, kind, action, children }) {
  return (
    <section>
      <div className="lane-head">
        <div>
          <h2 className="section-title">{title}</h2>
          <div className="lane-kind">{kind}</div>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function RuleRec({ rec }) {
  return (
    <article className={`rec rec-${rec.severity}`}>
      <span className="rec-rail" aria-hidden="true" />
      <div>
        <div className="spread">
          <h3 className="rec-title">{rec.title}</h3>
          <span className={`badge ${rec.severity === "high" ? "badge-occupied" : rec.severity === "medium" ? "badge-warn" : "badge-scan"}`}>
            {rec.severity === "high" ? "High priority" : rec.severity === "medium" ? "Worth a look" : "Low priority"}
          </span>
        </div>
        <p className="rec-detail">{rec.detail}</p>
        {rec.evidence?.length > 0 && (
          <div className="evidence">
            {rec.evidence.map((e) => (
              <span key={e.label}>
                {e.label} <b>{e.value}</b>
              </span>
            ))}
          </div>
        )}
        <div className="rec-rule">Rule: {rec.rule}</div>
      </div>
    </article>
  );
}

export function MeasuredList({ items }) {
  return (
    <div className="measured">
      {items.map((m) => (
        <div key={m.id}>
          <h3>{m.title}</h3>
          <p>
            {m.value_start ? `${clock(m.value_start)}–${clock(m.value_end)}. ` : ""}
            {m.detail}
          </p>
        </div>
      ))}
    </div>
  );
}

function EngineRecs() {
  const { data, error, reload } = useAsync(() => api.recommendations({ page_size: 50 }), []);
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);

  const act = async (fn, id, done) => {
    setBusy(id);
    setMsg(null);
    try {
      await fn();
      setMsg(done);
      await reload();
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(null);
    }
  };

  const items = data?.items || [];
  const pending = items.filter((r) => r.status === "PENDING");
  const resolved = items.filter((r) => r.status !== "PENDING").slice(0, 6);

  return (
    <Lane
      title="Seat allocation engine"
      kind="Rules over stored hourly occupancy snapshots: reduce below 60% average use, expand above 90%. Approving changes the team's seat allocation."
      action={
        <button type="button" className="btn btn-sm" disabled={busy === "scan"} onClick={() => act(api.scanRecommendations, "scan", "Scan complete.")}>
          <Icon name="refresh" /> {busy === "scan" ? "Scanning" : "Run scan"}
        </button>
      }
    >
      {msg && (
        <div className="notice small" role="status" style={{ marginBottom: 12 }}>
          {msg}
        </div>
      )}
      {error && <ErrorState error={error} onRetry={reload} />}
      {!data && !error && <Skeleton height={120} />}
      {data && !pending.length && (
        <EmptyState title="Nothing waiting for a decision">
          The engine needs snapshot history. Snapshots currently come from the seeded example data only, so live videos don't feed this engine yet.
        </EmptyState>
      )}
      <div className="rec-list">
        {pending.map((r) => (
          <article key={r.id} className={`rec rec-${r.priority === "HIGH" || r.priority === "CRITICAL" ? "high" : "medium"}`}>
            <span className="rec-rail" aria-hidden="true" />
            <div>
              <div className="spread">
                <h3 className="rec-title">{r.title}</h3>
                <div className="row">
                  {r.data?.demo && <DemoBadge title="Generated from seeded demo snapshots" />}
                  <span className="badge">{r.recommendation_type.charAt(0) + r.recommendation_type.slice(1).toLowerCase()}</span>
                </div>
              </div>
              <p className="rec-detail">{r.description}</p>
              <div className="evidence">
                {r.impact_seats !== null && (
                  <span>
                    Seats <b>{r.recommendation_type === "REDUCTION" ? `−${Math.abs(r.impact_seats)}` : `+${Math.abs(r.impact_seats)}`}</b>
                  </span>
                )}
                {r.impact_revenue !== null && (
                  <span>
                    Monthly impact <b>${num(r.impact_revenue)}</b>
                  </span>
                )}
                {r.startup_name && (
                  <span>
                    Team <b>{r.startup_name}</b>
                  </span>
                )}
              </div>
              <div className="row" style={{ marginTop: 12 }}>
                <button type="button" className="btn btn-primary btn-sm" disabled={!!busy} onClick={() => act(() => api.approveRecommendation(r.id), r.id, "Approved. Allocations updated.")}>
                  <Icon name="check" /> Approve
                </button>
                <button type="button" className="btn btn-ghost btn-sm" disabled={!!busy} onClick={() => act(() => api.rejectRecommendation(r.id), r.id, "Rejected.")}>
                  Reject
                </button>
              </div>
            </div>
          </article>
        ))}
      </div>
      {resolved.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div className="small muted" style={{ marginBottom: 6 }}>
            Recently decided
          </div>
          <ul className="small" style={{ listStyle: "none", display: "grid", gap: 4 }}>
            {resolved.map((r) => (
              <li key={r.id} className="spread">
                <span>{r.title}</span>
                <span className="faint">
                  {r.status.charAt(0) + r.status.slice(1).toLowerCase()} {r.resolved_at ? dateTime(r.resolved_at) : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Lane>
  );
}

function Forecast({ buildingId }) {
  const { data, error } = useAsync(() => api.forecast(buildingId, 2), [buildingId]);
  if (error || !data?.length) return null;
  const pts = data.map((d) => ({ time: d.timestamp, value: d.predicted_occupancy_rate }));
  return (
    <Lane
      title="Statistical forecast"
      kind="Seasonal average for each weekday and hour plus a capped linear trend, computed from stored snapshots. Not a trained model."
      action={<DemoBadge title="Built from seeded demo snapshots" />}
    >
      <div className="panel">
        <WhenVisible minHeight={220}>
          <TimeArea id="fc" data={pts} xKey="time" yKey="value" height={220} xFormat={(t) => dateTime(t)} yLabel="Predicted occupancy" color="var(--text-2)" />
        </WhenVisible>
      </div>
    </Lane>
  );
}

export default function Recommendations() {
  const ws = useWorkspace();
  const [range, setRange] = useState(168);
  const insights = useAsync(
    () => api.insights(ws.buildingId, { range_hours: range, include_demo: ws.includeDemo }),
    [ws.buildingId, range, ws.includeDemo],
    { enabled: !!ws.buildingId }
  );
  const d = insights.data;

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Recommendations</h1>
          <p className="page-lede">
            What the measurements suggest. Facts, rule-based advice and the allocation engine are kept apart so you can see where each suggestion comes from.
          </p>
        </div>
        <div className="page-actions">
          {d?.sources?.include_demo && d?.sources?.demo_available && <DemoBadge />}
          <Segmented id="rec-range" label="Analysis window" options={RANGES} value={range} onChange={setRange} />
        </div>
      </header>

      <div className="lanes">
        <Lane title="Measured insights" kind="Computed directly from observed seat time. No interpretation.">
          {insights.error && <ErrorState error={insights.error} onRetry={insights.reload} />}
          {!d && !insights.error && <Skeleton height={140} />}
          {d && !d.coverage.enough_data && (
            <EmptyState
              title="Not enough data available yet"
              action={
                <Link to="/" className="btn btn-sm">
                  <Icon name="upload" /> Analyze a video
                </Link>
              }
            >
              Insights need at least {d.coverage.min_observed_seat_minutes} seat-minutes of observation in this window. So far:{" "}
              {num(d.coverage.observed_seat_hours * 60, 1)} seat-minutes.
            </EmptyState>
          )}
          {d?.coverage.enough_data && (
            <Reveal>
              <MeasuredList items={d.measured} />
            </Reveal>
          )}
        </Lane>

        {d?.coverage.enough_data && (
          <Lane
            title="Rule-based recommendations"
            kind={`Fixed rules applied to ${num(d.coverage.observed_seat_hours, 1)} observed seat-hours across ${d.coverage.observed_seats} seats.`}
          >
            {d.recommendations.length ? (
              <div className="rec-list">
                {d.recommendations.map((r, i) => (
                  <Reveal key={r.id} delay={i * 0.04}>
                    <RuleRec rec={r} />
                  </Reveal>
                ))}
              </div>
            ) : (
              <EmptyState title="No rule applies to this window">
                Each rule needs enough observation to be fair, for example 30 minutes per seat before calling a seat idle. Short clips
                rarely meet that; longer recordings will.
              </EmptyState>
            )}
          </Lane>
        )}

        <EngineRecs />

        {ws.buildingId && ws.includeDemo && <Forecast buildingId={ws.buildingId} />}

        <Lane title="Learned recommendations" kind="Not built yet.">
          <p className="muted" style={{ maxWidth: "70ch" }}>
            The project roadmap includes vacancy forecasting with a trained time-series model and allocation suggestions learned from
            history. Those need weeks of real observation first, so nothing on this page is produced by a learned model today.
          </p>
        </Lane>
      </div>
    </div>
  );
}
