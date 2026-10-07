/** Seat matrix: one tile per seat, sorted by the parent. */

import { memo } from "react";
import { useSeatPulse, useSeatStatus } from "../../lib/live/store";
import { statusLabel, pct } from "../../lib/format";
import { StatusDot } from "../ui";
import "./data.css";

const Tile = memo(function Tile({ seat, cameraId, onSelect, selected }) {
  const live = useSeatStatus(cameraId, seat.seat_id);
  const pulse = useSeatPulse(cameraId, seat.seat_id);
  const status = cameraId && live !== "UNKNOWN" ? live : seat.status || "UNKNOWN";
  const cls = status === "OCCUPIED" ? "occupied" : status === "VACANT" ? "available" : "unknown";
  return (
    <button
      type="button"
      className={`tile tile-${cls}${selected ? " tile-selected" : ""}`}
      onClick={() => onSelect?.(seat)}
      aria-label={`${seat.label}, ${statusLabel[status]}${seat.startup_name ? `, ${seat.startup_name}` : ""}`}
    >
      {pulse > 0 && Date.now() - pulse < 4000 && <span key={pulse} className="tile-pulse" aria-hidden="true" />}
      <span className="tile-head">
        <span className="tile-label">{seat.label}</span>
        <StatusDot status={status} />
      </span>
      <span className="tile-meta">{seat.startup_name || statusLabel[status]}</span>
      {seat.utilization_pct !== undefined && seat.utilization_pct !== null && (
        <span className="tile-util">{pct(seat.utilization_pct)} used</span>
      )}
    </button>
  );
});

export default function SeatGrid({ seats, cameraId = null, onSelect, selectedId }) {
  return (
    <div className="seat-grid">
      {seats.map((s) => (
        <Tile key={s.seat_id} seat={s} cameraId={cameraId} onSelect={onSelect} selected={selectedId === s.seat_id} />
      ))}
    </div>
  );
}
