/**
 * Insights — a one-screen health check of the workspace.
 * Scores are simple, published formulas over measured data.
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/endpoints";
import { useWorkspace } from "../lib/workspace";
import { useAsync } from "../lib/useAsync";
import { num } from "../lib/format";
import { Gauge } from "../components/data/charts";
import { CountUp, Reveal } from "../components/motion";
import { DemoBadge, Segmented } from "../components/ui";
import { EmptyState, ErrorState, Skeleton } from "../components/feedback";
import { MeasuredList, RuleRec } from "./Recommendations";
import Icon from "../components/ui/Icon";
import "./pages.css";

const RANGES = [
  { value: 24, label: "24 h" },
  { value: 168, label: "7 days" },
];

export default function Insights() {
  const ws = useWorkspace();
  const [range, setRange] = useState(168);
  const { data: d, error, reload } = useAsync(
    () => api.insights(ws.buildingId, { range_hours: range, include_demo: ws.includeDemo }),
    [ws.buildingId, range, ws.includeDemo],
    { enabled: !!ws.buildingId }
  );

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Workspace insights</h1>
          <p className="page-lede">A health check built from measured occupancy. Every score shows the formula behind it.</p>
        </div>
        <div className="page-actions">
          {d?.sources?.include_demo && d?.sources?.demo_available && <DemoBadge />}
          <Segmented id="ins-range" label="Analysis window" options={RANGES} value={range} onChange={setRange} />
        </div>
      </header>

      {error && <ErrorState error={error} onRetry={reload} />}
      {!d && !error && <Skeleton height={260} />}

      {d && !d.coverage.enough_data && (
        <EmptyState
          title="Not enough data available yet"
          action={
            <Link to="/" className="btn btn-sm">
              <Icon name="upload" /> Analyze a video
            </Link>
          }
        >
          The health check needs at least {d.coverage.min_observed_seat_minutes} seat-minutes of observation in this window.
        </EmptyState>
      )}

      {d?.coverage.enough_data && d.health && (
        <>
          <Reveal className="panel health">
            <div className="health-score">
              <Gauge value={d.health.score} size={220} label="Workspace health" />
              <span className="gauge-value num">
                <CountUp value={d.health.score} />
              </span>
            </div>
            <div>
              <h2 className="section-title">Workspace health</h2>
              <p className="section-sub" style={{ marginBottom: 20 }}>
                {d.health.formula}
              </p>
              <div className="components">
                {d.health.components.map((c) => (
                  <div key={c.key} className="component-row">
                    <span className="small">{c.label}</span>
                    <span className="util-bar-track" style={{ height: 6 }}>
                      <span
                        className="util-bar-fill"
                        style={{
                          display: "block",
                          width: `${c.score}%`,
                          background: c.score >= 70 ? "var(--available)" : c.score >= 40 ? "var(--warn)" : "var(--occupied)",
                        }}
                      />
                    </span>
                    <span className="num small" style={{ textAlign: "right" }}>
                      {num(c.score)}
                    </span>
                    <span className="component-explain">{c.explain}</span>
                  </div>
                ))}
              </div>
            </div>
          </Reveal>

          <div className="stat-row section">
            <div className="stat">
              <div className="stat-label">Observed seats</div>
              <div className="stat-value">
                {d.coverage.observed_seats}
                <small>of {d.coverage.total_seats}</small>
              </div>
            </div>
            <div className="stat">
              <div className="stat-label">Observation</div>
              <div className="stat-value">
                {num(d.coverage.observed_seat_hours, 1)}
                <small>seat-h</small>
              </div>
            </div>
            <div className="stat">
              <div className="stat-label">Sessions</div>
              <div className="stat-value">{d.coverage.sessions}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Recommendations</div>
              <div className="stat-value">{d.recommendations.length}</div>
            </div>
          </div>

          <div className="grid-12 section">
            <section className="col-6">
              <h2 className="section-title" style={{ marginBottom: 12 }}>
                Capacity warnings
              </h2>
              {d.warnings.length ? (
                d.warnings.map((w) => (
                  <div key={w.id} className="notice notice-warn">
                    <div>
                      <strong>{w.title}.</strong> {w.detail}
                    </div>
                  </div>
                ))
              ) : (
                <p className="muted small">No seat area is near capacity right now.</p>
              )}
            </section>
            <section className="col-6">
              <h2 className="section-title" style={{ marginBottom: 12 }}>
                Unusual activity
              </h2>
              {d.unusual.length ? (
                <div style={{ display: "grid", gap: 8 }}>
                  {d.unusual.map((u) => (
                    <div key={u.id} className="notice">
                      <div>
                        <strong>{u.title}.</strong> {u.detail}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted small">Nothing unusual: no flickering seats and no unbroken sessions over four hours.</p>
              )}
            </section>
          </div>

          <section className="section">
            <h2 className="section-title" style={{ marginBottom: 12 }}>
              Measured
            </h2>
            <MeasuredList items={d.measured} />
          </section>

          {d.recommendations.length > 0 && (
            <section className="section">
              <div className="section-head">
                <h2 className="section-title">Top opportunities</h2>
                <Link to="/recommendations" className="btn btn-sm">
                  All recommendations
                </Link>
              </div>
              <div className="rec-list">
                {d.recommendations.slice(0, 3).map((r) => (
                  <RuleRec key={r.id} rec={r} />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
