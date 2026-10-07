/**
 * Recent seat changes. Live transitions from the WebSocket appear instantly;
 * stored changes from the API fill in history after a refresh.
 */

import { useMemo } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { StatusDot } from "../../components/ui";
import { EmptyState } from "../../components/feedback";
import { clock, relative, videoTime } from "../../lib/format";
import "./activity.css";

export default function ActivityFeed({ live = [], stored = [], limit = 12, onSelect }) {
  const reduce = useReducedMotion();
  const items = useMemo(() => {
    const seen = new Set();
    const out = [];
    for (const it of [...live, ...stored]) {
      // Live and stored copies of one change differ by milliseconds in `at`;
      // identify a change by seat, new state and position in its session.
      const key =
        it.video_ts !== null && it.video_ts !== undefined
          ? `${it.session_id || ""}-${it.seat_id}-${it.to}-${Math.round(it.video_ts * 10)}`
          : `${it.seat_id}-${it.to}-${(it.at || "").slice(0, 19)}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(it);
    }
    out.sort((a, b) => new Date(b.at) - new Date(a.at));
    return out.slice(0, limit);
  }, [live, stored, limit]);

  if (!items.length) {
    return (
      <EmptyState title="No seat changes yet">
        Changes appear here the moment a seat is taken or freed during an analysis.
      </EmptyState>
    );
  }

  return (
    <ol className="feed" aria-live="polite">
      <AnimatePresence initial={false}>
        {items.map((it) => (
          <motion.li
            key={`${it.seat_id}-${it.at}-${it.to}`}
            layout={!reduce}
            initial={reduce ? false : { opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={reduce ? undefined : { opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="feed-item"
          >
            <StatusDot status={it.to} />
            <div className="feed-body">
              <button type="button" className="feed-seat mono" onClick={() => onSelect?.(it)} disabled={!onSelect}>
                {it.label}
              </button>
              <span>{it.to === "OCCUPIED" ? "was taken" : "was freed"}</span>
              {it.startup_name && <span className="faint">({it.startup_name})</span>}
              {it.demo && <span className="badge badge-warn">Demo</span>}
            </div>
            <div className="feed-time">
              {it.video_ts !== null && it.video_ts !== undefined && <span className="mono">{videoTime(it.video_ts)} in video</span>}
              <span title={clock(it.at, true)}>{relative(it.at)}</span>
            </div>
          </motion.li>
        ))}
      </AnimatePresence>
    </ol>
  );
}
