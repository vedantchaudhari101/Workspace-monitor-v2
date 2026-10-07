/**
 * Explorer — the physical workspace, floor by floor. Seat positions come from
 * the camera frame (detected seats) or the stored layout (other seats).
 */

import { useMemo, useState } from "react";
import { api } from "../api/endpoints";
import { useWorkspace } from "../lib/workspace";
import { useAsync } from "../lib/useAsync";
import { compareLabels, pct } from "../lib/format";
import { apiUrl } from "../api/client";
import SeatMap from "../components/data/SeatMap";
import SeatGrid from "../components/data/SeatGrid";
import { Reveal } from "../components/motion";
import { DemoBadge, Segmented, StatusDot } from "../components/ui";
import { EmptyState, ErrorState, Skeleton } from "../components/feedback";
import SeatDrawer from "../features/seats/SeatDrawer";
import "./pages.css";

const UTIL = {
  any: () => true,
  low: (v) => v !== null && v !== undefined && v < 20,
  mid: (v) => v !== null && v !== undefined && v >= 20 && v <= 80,
  high: (v) => v !== null && v !== undefined && v > 80,
  none: (v) => v === null || v === undefined,
};

export default function Explorer() {
  const ws = useWorkspace();
  const [view, setView] = useState("map");
  const [status, setStatus] = useState("all");
  const [team, setTeam] = useState("all");
  const [zone, setZone] = useState("all");
  const [util, setUtil] = useState("any");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null);

  const { data, error, reload } = useAsync(
    () => api.map(ws.buildingId, { range_hours: 24, include_demo: ws.includeDemo }),
    [ws.buildingId, ws.includeDemo],
    { enabled: !!ws.buildingId }
  );

  const zones = useMemo(() => (data?.floors || []).flatMap((f) => f.zones.map((z) => ({ ...z, floor: f.name }))), [data]);

  const match = (s) =>
    (status === "all" || s.status === status) &&
    (team === "all" || (team === "none" ? !s.startup_id : s.startup_id === team)) &&
    UTIL[util](s.utilization_pct) &&
    (!query || s.label.toLowerCase().includes(query.toLowerCase()));

  const totals = useMemo(() => {
    const all = zones.flatMap((z) => z.seats);
    return {
      seats: all.length,
      matching: all.filter(match).length,
      occupied: all.filter((s) => s.status === "OCCUPIED").length,
      available: all.filter((s) => s.status === "VACANT").length,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zones, status, team, util, query]);

  const shown = zones.filter((z) => zone === "all" || z.zone_id === zone);

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1 className="page-title">Workspace explorer</h1>
          <p className="page-lede">
            Every tracked seat, where it sits, who it belongs to and how much it was used in the last 24 hours. Select a seat to see its history or assign it to a team.
          </p>
        </div>
        <div className="page-actions">
          {data?.sources?.include_demo && data?.sources?.demo_available && <DemoBadge />}
          <Segmented
            id="explorer-view"
            label="View"
            options={[
              { value: "map", label: "Map" },
              { value: "grid", label: "Grid" },
            ]}
            value={view}
            onChange={setView}
          />
        </div>
      </header>

      <div className="filters" role="search" aria-label="Filter seats">
        <div className="field">
          <label htmlFor="f-q">Seat</label>
          <input id="f-q" className="input" placeholder="Search label" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="f-status">Status</label>
          <select id="f-status" className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="all">Any</option>
            <option value="OCCUPIED">Occupied</option>
            <option value="VACANT">Available</option>
            <option value="UNKNOWN">Not observed</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="f-team">Team</label>
          <select id="f-team" className="select" value={team} onChange={(e) => setTeam(e.target.value)}>
            <option value="all">Any</option>
            <option value="none">Unassigned</option>
            {ws.startups.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="f-zone">Zone</label>
          <select id="f-zone" className="select" value={zone} onChange={(e) => setZone(e.target.value)}>
            <option value="all">All zones</option>
            {zones.map((z) => (
              <option key={z.zone_id} value={z.zone_id}>
                {z.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="f-util">Utilization, 24 h</label>
          <select id="f-util" className="select" value={util} onChange={(e) => setUtil(e.target.value)}>
            <option value="any">Any</option>
            <option value="low">Below 20%</option>
            <option value="mid">20% to 80%</option>
            <option value="high">Above 80%</option>
            <option value="none">Not observed</option>
          </select>
        </div>
        <div className="small muted" style={{ marginLeft: "auto", paddingBottom: 10 }} role="status">
          {totals.matching} of {totals.seats} seats
        </div>
      </div>

      {error && <ErrorState error={error} onRetry={reload} />}
      {!data && !error && <Skeleton height={360} />}
      {data && !zones.length && (
        <EmptyState title="No seats yet">
          Seats are created when a video is calibrated on the live page.
          {ws.demoDataPresent && !ws.includeDemo && " Switch on demo data to explore the seeded example building."}
        </EmptyState>
      )}

      {shown.map((z, i) => {
        const seats = [...z.seats].sort((a, b) => compareLabels(a.label, b.label));
        const visible = seats.filter(match);
        const occ = seats.filter((s) => s.status === "OCCUPIED").length;
        const obs = seats.filter((s) => s.status !== "UNKNOWN").length;
        const avgUtil = seats.filter((s) => s.utilization_pct !== null && s.utilization_pct !== undefined);
        return (
          <Reveal key={z.zone_id} className="zone-block" delay={i * 0.04}>
            <div className="zone-head">
              <div>
                <h2 className="panel-title">{z.name}</h2>
                <div className="panel-sub">
                  {z.floor}
                  {z.camera ? `, seen by ${z.camera.name}` : ""}
                </div>
              </div>
              <div className="row small muted">
                <span className="row" style={{ gap: 6 }}>
                  <StatusDot status={obs ? "OCCUPIED" : "UNKNOWN"} /> {obs ? `${occ} occupied` : "not observed now"}
                </span>
                <span>{seats.length} seats</span>
                <span>
                  {avgUtil.length ? `${pct(avgUtil.reduce((a, s) => a + s.utilization_pct, 0) / avgUtil.length)} average use` : "no use measured"}
                </span>
              </div>
            </div>
            <div className="panel">
              {view === "map" ? (
                <SeatMap
                  seats={seats}
                  frameW={z.camera?.frame_w}
                  frameH={z.camera?.frame_h}
                  background={z.camera?.has_snapshot ? apiUrl(`/api/v1/occupancy/camera/${z.camera.id}/snapshot`) : undefined}
                  onSelect={(s) => setSelected(s.seat_id)}
                  selectedId={selected}
                  isDim={(s) => !match(s)}
                  ariaLabel={`Seats in ${z.name}`}
                />
              ) : visible.length ? (
                <SeatGrid seats={visible} onSelect={(s) => setSelected(s.seat_id)} selectedId={selected} />
              ) : (
                <p className="small muted">No seats in this zone match the filters.</p>
              )}
            </div>
          </Reveal>
        );
      })}

      <SeatDrawer seatId={selected} onClose={() => setSelected(null)} onChanged={reload} />
    </div>
  );
}
