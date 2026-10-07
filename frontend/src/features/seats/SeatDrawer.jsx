/**
 * Seat detail: live status, team assignment, measured history and the raw
 * state changes the pipeline recorded for this seat.
 */

import { useState } from "react";
import Drawer from "@mui/material/Drawer";
import { api } from "../../api/endpoints";
import { useAsync } from "../../lib/useAsync";
import { useWorkspace } from "../../lib/workspace";
import { useSeatStatus } from "../../lib/live/store";
import { clock, dateTime, duration, pct, statusLabel, videoTime } from "../../lib/format";
import { Segmented, StatusBadge } from "../../components/ui";
import { ErrorState, Skeleton } from "../../components/feedback";
import { IntervalBar } from "../../components/data/charts";
import Icon from "../../components/ui/Icon";
import "./seats.css";

const RANGES = [
  { value: 1, label: "1 h" },
  { value: 24, label: "24 h" },
  { value: 168, label: "7 days" },
];

function Body({ seatId, cameraId, onChanged }) {
  const ws = useWorkspace();
  const [range, setRange] = useState(24);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const live = useSeatStatus(cameraId, seatId);
  const { data, error, loading, reload } = useAsync(
    () => api.seatHistory(seatId, { range_hours: range, include_demo: ws.includeDemo }),
    [seatId, range, ws.includeDemo]
  );

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data) {
    return (
      <div style={{ display: "grid", gap: 12 }}>
        <Skeleton height={36} width="40%" />
        <Skeleton height={80} />
        <Skeleton height={200} />
      </div>
    );
  }

  const seat = data.seat;
  const st = data.stats;
  const status = cameraId && live !== "UNKNOWN" ? live : st.current_status;
  const transitions = data.events.filter((e, i, arr) => i === 0 || e.status !== arr[i - 1].status).slice(-40).reverse();

  const assign = async (startupId) => {
    setBusy(true);
    setMsg(null);
    try {
      if (seat.allocation_id) await api.releaseAllocation(seat.allocation_id);
      if (startupId) await api.allocateSeat(seat.seat_id, startupId);
      setMsg(startupId ? "Team assigned." : "Seat unassigned.");
      await reload();
      onChanged?.();
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="drawer-body">
      <div className="spread">
        <div>
          <div className="drawer-title mono">{seat.seat_label}</div>
          <div className="small muted">
            {seat.zone}
            {seat.floor ? `, ${seat.floor}` : ""}
          </div>
        </div>
        <StatusBadge status={status} />
      </div>

      {!seat.is_active && (
        <div className="notice notice-warn small">This seat wasn't found in the latest calibration and is no longer tracked.</div>
      )}

      <div className="field">
        <label htmlFor="assign-team">Team</label>
        <select
          id="assign-team"
          className="select"
          value={seat.startup_id || ""}
          disabled={busy || !ws.startups.length}
          onChange={(e) => assign(e.target.value || null)}
        >
          <option value="">Unassigned</option>
          {ws.startups.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        {!ws.startups.length && <span className="xs faint">No teams exist yet. Add startups through the API to assign seats.</span>}
        {msg && <span className="xs muted" role="status">{msg}</span>}
      </div>

      <div className="spread">
        <span className="small muted">Measured over</span>
        <Segmented id="seat-range" label="History range" options={RANGES} value={range} onChange={setRange} />
      </div>

      <dl className="seat-stats">
        <div>
          <dt>Utilization</dt>
          <dd>{pct(st.utilization_pct)}</dd>
        </div>
        <div>
          <dt>Occupied</dt>
          <dd>{duration(st.occupied_s)}</dd>
        </div>
        <div>
          <dt>Vacant</dt>
          <dd>{duration(st.vacant_s)}</dd>
        </div>
        <div>
          <dt>Sessions</dt>
          <dd>{st.sessions}</dd>
        </div>
        <div>
          <dt>Average session</dt>
          <dd>{duration(st.avg_session_s)}</dd>
        </div>
        <div>
          <dt>Longest session</dt>
          <dd>{duration(st.longest_session_s)}</dd>
        </div>
        <div>
          <dt>Current session</dt>
          <dd>{st.current_session_s ? duration(st.current_session_s) : "—"}</dd>
        </div>
        <div>
          <dt>Last occupied</dt>
          <dd className="small">{st.last_occupied ? dateTime(st.last_occupied) : "—"}</dd>
        </div>
      </dl>

      <div>
        <div className="small muted" style={{ marginBottom: 6 }}>
          Timeline (red occupied, green available, gaps not observed)
        </div>
        <IntervalBar intervals={data.intervals} since={data.window.since} until={data.window.until} />
        <div className="spread xs faint" style={{ marginTop: 4 }}>
          <span>{dateTime(data.window.since)}</span>
          <span>now</span>
        </div>
      </div>

      <div>
        <div className="panel-title" style={{ marginBottom: 8 }}>
          State changes
        </div>
        {loading && <Skeleton height={60} />}
        {!transitions.length ? (
          <p className="small muted">No observations in this window.</p>
        ) : (
          <ol className="seat-log">
            {transitions.map((e, i) => (
              <li key={i}>
                <span className="mono">{clock(e.at, true)}</span>
                <span className={`log-status log-${e.status}`}>{statusLabel[e.status]}</span>
                <span className="faint xs">
                  {e.video_ts !== null && e.video_ts !== undefined ? `${videoTime(e.video_ts)} in video` : e.source !== "VIDEO" ? "demo" : ""}
                </span>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

export default function SeatDrawer({ seatId, cameraId, onClose, onChanged }) {
  return (
    <Drawer anchor="right" open={!!seatId} onClose={onClose} PaperProps={{ sx: { width: { xs: "100%", sm: 420 } } }}>
      <div className="drawer-head">
        <span className="small muted">Seat details</span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close seat details">
          <Icon name="close" />
        </button>
      </div>
      {seatId && <Body seatId={seatId} cameraId={cameraId} onChanged={onChanged} />}
    </Drawer>
  );
}
