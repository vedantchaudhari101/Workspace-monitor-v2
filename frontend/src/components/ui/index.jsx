/** Small UI primitives shared by every page. */

import { motion, useReducedMotion } from "motion/react";
import Tooltip from "@mui/material/Tooltip";
import { statusLabel } from "../../lib/format";

export function Segmented({ options, value, onChange, label, id }) {
  const reduce = useReducedMotion();
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button key={o.value} type="button" aria-pressed={active} onClick={() => onChange(o.value)}>
            {active && (
              <motion.span
                layoutId={`seg-${id || label}`}
                className="seg-thumb"
                transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 34 }}
              />
            )}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export function Toggle({ checked, onChange, children }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="toggle-track" aria-hidden="true" />
      {children}
    </label>
  );
}

export function StatusDot({ status, className = "" }) {
  const cls = status === "OCCUPIED" ? "dot-occupied" : status === "VACANT" ? "dot-available" : "dot-unknown";
  return <span className={`dot ${cls} ${className}`} aria-hidden="true" />;
}

export function StatusBadge({ status }) {
  const cls = status === "OCCUPIED" ? "badge-occupied" : status === "VACANT" ? "badge-available" : "";
  return (
    <span className={`badge ${cls}`}>
      <StatusDot status={status} />
      {statusLabel[status] || status}
    </span>
  );
}

export function DemoBadge({ title = "Seeded or simulated data, not computer-vision output" }) {
  return (
    <Tooltip title={title}>
      <span className="badge badge-warn" tabIndex={0}>
        Demo data
      </span>
    </Tooltip>
  );
}

export function Stat({ label, value, note, title }) {
  return (
    <div className="stat" title={title}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {note && <div className="stat-note">{note}</div>}
    </div>
  );
}

export function UtilBar({ value }) {
  if (value === null || value === undefined) return <span className="muted">—</span>;
  const tone = value >= 85 ? "var(--occupied)" : value < 20 ? "var(--text-3)" : "var(--text-2)";
  return (
    <span className="util-bar">
      <span className="util-bar-track">
        <span className="util-bar-fill" style={{ width: `${Math.min(100, value)}%`, background: tone, display: "block" }} />
      </span>
      <span className="num" style={{ minWidth: 38, textAlign: "right" }}>
        {value.toFixed(0)}%
      </span>
    </span>
  );
}
