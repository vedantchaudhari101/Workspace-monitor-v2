/** Full summary for one analysis session. */

import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/endpoints";
import { useAsync } from "../lib/useAsync";
import { dateTime, videoTime } from "../lib/format";
import SessionSummary, { Diagnostics, SummarySeats } from "../features/analysis/SessionSummary";
import SeatDrawer from "../features/seats/SeatDrawer";
import { EmptyState, ErrorState, Skeleton } from "../components/feedback";
import Icon from "../components/ui/Icon";
import "./pages.css";

export default function Session() {
  const { sessionId } = useParams();
  const [selected, setSelected] = useState(null);
  const { data, error, reload } = useAsync(() => api.session(sessionId), [sessionId]);

  return (
    <div className="page">
      <Link to="/analytics" className="btn btn-ghost btn-sm" style={{ marginBottom: 16, marginLeft: -12 }}>
        <Icon name="arrowLeft" /> Analytics
      </Link>
      {error && <ErrorState error={error} onRetry={reload} title="Couldn't load this session" />}
      {!data && !error && <Skeleton height={320} />}
      {data && (
        <>
          <header className="page-head">
            <div>
              <h1 className="page-title">{data.source_filename || "Analysis session"}</h1>
              <p className="page-lede">
                Processed {dateTime(data.created_at)}. {data.frame_w && `${data.frame_w}×${data.frame_h}, `}
                {videoTime(data.video_duration_s)} long, {data.pipeline === "legacy" ? "legacy pipeline" : "report pipeline"}.
              </p>
            </div>
          </header>
          {data.summary ? (
            <>
              <section className="panel">
                <SessionSummary summary={data.summary} status={data.status} session={data} />
              </section>
              <section className="section">
                <div className="section-head">
                  <div>
                    <h2 className="section-title">Seats in this video</h2>
                    <p className="section-sub">Times are positions in the video.</p>
                  </div>
                </div>
                <SummarySeats summary={data.summary} onSelect={(s) => setSelected(s.seat_id)} />
              </section>
              <section className="section">
                <div className="section-head">
                  <div>
                    <h2 className="section-title">How the pipeline ran</h2>
                    <p className="section-sub">Calibration diagnostics and throughput for this run.</p>
                  </div>
                </div>
                <div className="panel">
                  <Diagnostics summary={data.summary} />
                </div>
              </section>
            </>
          ) : (
            <EmptyState title="No summary for this session">{data.error || "The run ended before a summary could be produced."}</EmptyState>
          )}
        </>
      )}
      <SeatDrawer seatId={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
