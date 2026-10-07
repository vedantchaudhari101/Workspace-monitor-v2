/**
 * Seat map drawn in the camera's own pixel space: every seat sits where the
 * calibration engine found it in the frame. Seats without coordinates fall
 * back to an evenly spaced grid.
 */

import { memo, useMemo } from "react";
import { useSeatPulse, useSeatStatus } from "../../lib/live/store";
import { statusLabel } from "../../lib/format";
import "./data.css";

function normBox(b) {
  if (!b) return null;
  if (b.x1 !== undefined) return { x: b.x1, y: b.y1, w: b.x2 - b.x1, h: b.y2 - b.y1 };
  if (b.x !== undefined && b.w) return { x: b.x, y: b.y, w: b.w, h: b.h };
  return null;
}

function gridLayout(seats) {
  const cols = Math.max(1, Math.ceil(Math.sqrt(seats.length * 1.6)));
  const cell = 100;
  return {
    boxes: seats.map((_, i) => ({ x: (i % cols) * cell + 12, y: Math.floor(i / cols) * cell + 12, w: cell - 24, h: cell - 30 })),
    w: cols * cell,
    h: Math.ceil(seats.length / cols) * cell,
  };
}

const SeatShape = memo(function SeatShape({ seat, box, cameraId, scale, selected, onSelect, dim }) {
  const liveStatus = useSeatStatus(cameraId, seat.seat_id);
  const pulse = useSeatPulse(cameraId, seat.seat_id);
  const status = cameraId && liveStatus !== "UNKNOWN" ? liveStatus : seat.status || "UNKNOWN";
  const cls = status === "OCCUPIED" ? "occupied" : status === "VACANT" ? "available" : "unknown";
  const label = `${seat.label}: ${statusLabel[status] || status}${seat.startup_name ? `, ${seat.startup_name}` : ""}`;
  const fontSize = Math.max(11, Math.min(box.h * 0.32, 22)) * scale;
  const r = Math.min(8 * scale, box.w / 6);

  return (
    <g
      className={`seat seat-${cls}${selected ? " seat-selected" : ""}${dim ? " seat-dim" : ""}`}
      role={onSelect ? "button" : "img"}
      tabIndex={onSelect ? 0 : undefined}
      aria-label={label}
      onClick={onSelect ? () => onSelect(seat) : undefined}
      onKeyDown={
        onSelect
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(seat);
              }
            }
          : undefined
      }
    >
      <title>{label}</title>
      {pulse > 0 && Date.now() - pulse < 4000 && (
        <rect key={pulse} className="seat-pulse" x={box.x} y={box.y} width={box.w} height={box.h} rx={r} />
      )}
      <rect className="seat-body" x={box.x} y={box.y} width={box.w} height={box.h} rx={r} strokeWidth={2 * scale} />
      <text className="seat-label" x={box.x + 6 * scale} y={box.y + fontSize + 4 * scale} fontSize={fontSize}>
        {seat.label}
      </text>
      {status === "OCCUPIED" && (
        <circle className="seat-marker" cx={box.x + box.w - 10 * scale} cy={box.y + 10 * scale} r={4 * scale} />
      )}
    </g>
  );
});

export default function SeatMap({ seats, frameW, frameH, cameraId = null, onSelect, selectedId, isDim, background, ariaLabel }) {
  const layout = useMemo(() => {
    const boxes = seats.map((s) => normBox(s.bbox));
    if (frameW && frameH && boxes.every(Boolean)) {
      return { boxes, w: frameW, h: frameH, framed: true };
    }
    if (boxes.length && boxes.every(Boolean)) {
      const maxX = Math.max(...boxes.map((b) => b.x + b.w)) + 40;
      const maxY = Math.max(...boxes.map((b) => b.y + b.h)) + 40;
      const minX = Math.max(0, Math.min(...boxes.map((b) => b.x)) - 40);
      const minY = Math.max(0, Math.min(...boxes.map((b) => b.y)) - 40);
      return { boxes, w: maxX - minX, h: maxY - minY, ox: minX, oy: minY, framed: false };
    }
    return { ...gridLayout(seats), framed: false };
  }, [seats, frameW, frameH]);

  const scale = Math.max(1, layout.w / 1200);
  const vb = `${layout.ox || 0} ${layout.oy || 0} ${layout.w} ${layout.h}`;

  return (
    <svg className="seat-map" viewBox={vb} style={layout.framed ? undefined : { maxWidth: Math.max(320, layout.w) }} role="group" aria-label={ariaLabel || "Seat map"} preserveAspectRatio="xMidYMid meet">
      {layout.framed && <rect className="seat-map-frame" x="0" y="0" width={layout.w} height={layout.h} rx={10 * scale} />}
      {background && layout.framed && (
        <image href={background} x="0" y="0" width={layout.w} height={layout.h} opacity="0.5" preserveAspectRatio="none" />
      )}
      {seats.map((s, i) => (
        <SeatShape
          key={s.seat_id}
          seat={s}
          box={layout.boxes[i]}
          cameraId={cameraId}
          scale={scale}
          selected={selectedId === s.seat_id}
          onSelect={onSelect}
          dim={isDim ? isDim(s) : false}
        />
      ))}
    </svg>
  );
}
