/**
 * The analysis console: upload a video, watch the pipeline work, and see the
 * annotated result. Every stage shown maps to a real backend event:
 *
 *   Upload            → HTTP upload progress
 *   Calibrate seats   → init_progress (frames scanned of the calibration window)
 *   Track occupancy   → processing_update (frame of total, inference rate)
 *   Summarize         → session_summary
 */

import { useCallback, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { api } from "../../api/endpoints";
import { apiUrl } from "../../api/client";
import { resetCamera } from "../../lib/live/store";
import { bytes, num, videoTime } from "../../lib/format";
import { Magnetic } from "../../components/motion";
import Icon from "../../components/ui/Icon";
import "./analysis.css";

const ACCEPT = [".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"];

function stageIndex(status, stage, uploading) {
  if (uploading) return 0;
  if (status === "PROCESSING" || stage === "CALIBRATING") return 1;
  if (status === "ANALYZING" || stage === "TRACKING") return 2;
  if (stage === "FINALIZING") return 3;
  if (status === "COMPLETED" || status === "STOPPED") return 4;
  return -1;
}

function PipelineStages({ cam, upload }) {
  const idx = stageIndex(cam.status, cam.stage, upload.active);
  const failed = cam.status === "FAILED" || upload.error;
  const cal = cam.calibration || {};
  const trackPct = cam.totalFrames ? Math.min(100, (cam.frame / cam.totalFrames) * 100) : 0;
  const steps = [
    {
      label: "Upload video",
      detail: upload.active
        ? `${Math.round(upload.progress * 100)}% of ${bytes(upload.total)}`
        : upload.name
          ? upload.name
          : "MP4, MOV, AVI, MKV or WebM",
      progress: upload.active ? upload.progress * 100 : idx > 0 ? 100 : 0,
    },
    {
      label: "Calibrate seats",
      detail:
        idx === 1
          ? `Scanning frame ${cal.frame || 0} of ${cal.total || "…"}`
          : idx > 1
            ? `${cam.seats.length} seats found`
            : "Find every chair in the first frames",
      progress: idx === 1 && cal.total ? (cal.frame / cal.total) * 100 : idx > 1 ? 100 : 0,
    },
    {
      label: "Track occupancy",
      detail:
        idx === 2
          ? `${num(trackPct)}% of the video, ${cam.fps ? `${cam.fps.toFixed(1)} checks/s` : "starting"}`
          : idx > 2
            ? `${num(cam.totalFrames)} frames processed`
            : "Pose tracking per seat",
      progress: idx === 2 ? trackPct : idx > 2 ? 100 : 0,
    },
    {
      label: "Summarize",
      detail: idx >= 4 ? (cam.status === "STOPPED" ? "Stopped early, partial summary" : "Summary ready") : "Durations, peaks, sessions",
      progress: idx >= 4 ? 100 : idx === 3 ? 50 : 0,
    },
  ];

  return (
    <ol className="stages" aria-label="Analysis progress">
      {steps.map((s, i) => {
        const state = failed && i === Math.max(0, idx) ? "failed" : i < idx ? "done" : i === idx ? "active" : "pending";
        return (
          <li key={s.label} className={`stage stage-${state}`} aria-current={state === "active" ? "step" : undefined}>
            <div className="stage-top">
              <span className="stage-index mono">{i + 1}</span>
              <span className="stage-label">{s.label}</span>
            </div>
            <div className="stage-detail">{s.detail}</div>
            <div className="stage-track" aria-hidden="true">
              <span style={{ width: `${s.progress}%` }} />
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function ScanPlaceholder({ title, children }) {
  return (
    <div className="scan-placeholder">
      <div className="scan-grid" aria-hidden="true" />
      <div className="scan-line" aria-hidden="true" />
      <div className="scan-copy">
        <div className="scan-title">{title}</div>
        {children}
      </div>
    </div>
  );
}

export default function AnalysisConsole({ cameraId, cam, maxUploadMb, onUploaded, sample }) {
  const reduce = useReducedMotion();
  const inputRef = useRef(null);
  const [drag, setDrag] = useState(false);
  const [upload, setUpload] = useState({ active: false, progress: 0, total: 0, name: null, error: null });
  const [stopping, setStopping] = useState(false);

  const running = ["PROCESSING", "ANALYZING"].includes(cam.status);
  const finished = ["COMPLETED", "STOPPED", "FAILED"].includes(cam.status);
  const busy = upload.active || running;

  const start = useCallback(
    async (file) => {
      if (!file || !cameraId) return;
      const ext = `.${file.name.split(".").pop().toLowerCase()}`;
      if (!ACCEPT.includes(ext)) {
        setUpload((u) => ({ ...u, error: `“${file.name}” isn't a supported video. Use ${ACCEPT.join(", ")}.` }));
        return;
      }
      if (file.size > maxUploadMb * 1024 * 1024) {
        setUpload((u) => ({ ...u, error: `This video is ${bytes(file.size)}. The limit is ${maxUploadMb} MB.` }));
        return;
      }
      setUpload({ active: true, progress: 0, total: file.size, name: file.name, error: null });
      resetCamera(cameraId, { status: "IDLE", stage: "IDLE", sourceFilename: file.name });
      try {
        const res = await api.uploadVideo(cameraId, file, (p) => setUpload((u) => ({ ...u, progress: p })));
        setUpload((u) => ({ ...u, active: false, progress: 1 }));
        resetCamera(cameraId, { status: "PROCESSING", stage: "CALIBRATING", sessionId: res.session_id, sourceFilename: file.name });
        onUploaded?.(res);
      } catch (e) {
        setUpload((u) => ({ ...u, active: false, error: e.message || "Upload failed." }));
      }
    },
    [cameraId, maxUploadMb, onUploaded]
  );

  const runSample = async () => {
    setUpload({ active: false, progress: 1, total: 0, name: sample.name, error: null });
    resetCamera(cameraId, { status: "PROCESSING", stage: "CALIBRATING", sourceFilename: sample.name });
    try {
      const res = await api.runSample(cameraId);
      resetCamera(cameraId, { status: "PROCESSING", stage: "CALIBRATING", sessionId: res.session_id, sourceFilename: sample.name });
      onUploaded?.(res);
    } catch (e) {
      resetCamera(cameraId, {});
      setUpload((u) => ({ ...u, error: e.message }));
    }
  };

  const stop = async () => {
    setStopping(true);
    try {
      await api.stopCamera(cameraId);
    } catch (e) {
      setUpload((u) => ({ ...u, error: e.message }));
    } finally {
      setStopping(false);
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDrag(false);
    if (busy) return;
    start(e.dataTransfer.files?.[0]);
  };

  const progress = cam.totalFrames ? cam.frame / cam.totalFrames : 0;
  const ts = cam.videoFps ? cam.frame / cam.videoFps : null;
  const duration = cam.videoFps && cam.totalFrames ? cam.totalFrames / cam.videoFps : null;
  const streamSrc = cam.sessionId ? apiUrl(`/api/v1/occupancy/camera/${cameraId}/stream?s=${cam.sessionId}`) : null;
  const frameSrc = cam.sessionId ? apiUrl(`/api/v1/occupancy/camera/${cameraId}/frame?s=${cam.sessionId}&f=${cam.status}`) : null;

  let view = "empty";
  if (upload.active) view = "uploading";
  else if (cam.status === "PROCESSING") view = "calibrating";
  else if (cam.status === "ANALYZING") view = "tracking";
  else if (finished && cam.sessionId) view = "finished";
  else if (cam.status === "SIMULATING") view = "simulating";

  return (
    <section className="console" aria-label="Video analysis">
      <div
        className={`stage-frame frame${drag ? " is-drag" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!busy) setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
      >
        <span className="frame-corners" />
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={view}
            className="stage-view"
            initial={reduce ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={reduce ? undefined : { opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            {view === "empty" && (
              <div className="dropzone">
                <div className="dropzone-copy">
                  <h2 className="dropzone-title">Upload a workspace video to begin analysis</h2>
                  <p className="muted small">
                    A fixed camera that can see the chairs works best. The first few seconds are used to find seats, so start
                    the clip with the room in view. Drop a file here or choose one.
                  </p>
                </div>
                <div className="row" style={{ flexWrap: "wrap" }}>
                  <Magnetic>
                    <button type="button" className="btn btn-primary" onClick={() => inputRef.current?.click()} disabled={!cameraId}>
                      <Icon name="upload" /> Choose video
                    </button>
                  </Magnetic>
                  {sample && (
                    <button type="button" className="btn" onClick={runSample} disabled={!cameraId}>
                      <Icon name="film" /> Try the sample video
                    </button>
                  )}
                  <span className="xs faint">Up to {maxUploadMb} MB</span>
                </div>
                {sample?.credit && <p className="xs faint">Sample: {sample.credit}</p>}
              </div>
            )}

            {view === "uploading" && (
              <ScanPlaceholder title="Uploading video">
                <div className="small muted">
                  {upload.name}, {Math.round(upload.progress * 100)}% of {bytes(upload.total)}
                </div>
              </ScanPlaceholder>
            )}

            {view === "calibrating" && (
              <ScanPlaceholder title="Analyzing workspace">
                <div className="small muted">
                  Finding seats: frame {cam.calibration?.frame || 0} of {cam.calibration?.total || "…"}
                </div>
              </ScanPlaceholder>
            )}

            {(view === "tracking" || view === "finished") && (
              <div className="video-wrap">
                <img
                  key={`${cam.sessionId}-${view}`}
                  src={view === "tracking" ? streamSrc : frameSrc}
                  alt={
                    view === "tracking"
                      ? "Live annotated video: seat boxes are red when occupied and green when available"
                      : "Last analysed frame"
                  }
                  className="video"
                />
                <div className="hud hud-top">
                  <span className="badge badge-scan">
                    <span className={`dot ${view === "tracking" ? "dot-live" : "dot-unknown"}`} />
                    {view === "tracking" ? "Analyzing" : cam.status === "COMPLETED" ? "Analysis complete" : cam.status === "STOPPED" ? "Stopped" : "Failed"}
                  </span>
                  <span className="hud-count num">
                    <strong>{cam.occupied ?? 0}</strong> of {cam.seats.length} seats occupied
                  </span>
                </div>
                <div className="hud hud-bottom">
                  <span className="mono xs">
                    {videoTime(view === "finished" ? duration : ts)} / {videoTime(duration)}
                  </span>
                  <div className="hud-track">
                    <span style={{ width: `${(view === "finished" ? 1 : progress) * 100}%` }} />
                  </div>
                  <span className="mono xs">{cam.inferenceMs ? `${Math.round(cam.inferenceMs)} ms/frame` : ""}</span>
                </div>
              </div>
            )}

            {view === "simulating" && (
              <ScanPlaceholder title="Simulated feed">
                <div className="small muted">This camera is running demo mode: seats change at random, there is no video.</div>
              </ScanPlaceholder>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT.join(",")}
        className="visually-hidden"
        onChange={(e) => {
          start(e.target.files?.[0]);
          e.target.value = "";
        }}
        aria-label="Choose a workspace video"
      />

      <div className="console-bar">
        <PipelineStages cam={cam} upload={upload} />
        <div className="console-actions">
          {running && (
            <button type="button" className="btn btn-danger btn-sm" onClick={stop} disabled={stopping}>
              <Icon name="stop" /> {stopping ? "Stopping" : "Stop analysis"}
            </button>
          )}
          {(finished || view === "simulating") && (
            <button type="button" className="btn btn-sm" onClick={() => inputRef.current?.click()}>
              <Icon name="upload" /> Analyze another video
            </button>
          )}
        </div>
      </div>

      {(upload.error || cam.error) && (
        <div className="notice notice-error" role="alert" style={{ marginTop: 12 }}>
          <Icon name="info" size={16} />
          <div>
            {upload.error || `The analysis stopped with an error: ${cam.error}`}{" "}
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setUpload((u) => ({ ...u, error: null }))}>
              Dismiss
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
