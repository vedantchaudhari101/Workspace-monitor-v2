/**
 * One shared WebSocket for the whole app.
 *
 * The original pages each opened their own socket and re-rendered the full
 * seat matrix on every message. This store keeps a single connection,
 * normalises messages per camera, and lets components subscribe to exactly
 * what they render (a single seat's status, a camera's progress, …) through
 * useSyncExternalStore, so a 5 Hz processing update only re-renders what
 * actually changed.
 */

import { useSyncExternalStore, useEffect } from "react";
import { wsUrl, getAuthToken } from "../../api/client";

const MAX_TRANSITIONS = 60;
const MAX_TIMELINE = 600;

const emptyCamera = () => ({
  status: "IDLE",
  stage: "IDLE",
  sessionId: null,
  demo: false,
  frameW: null,
  frameH: null,
  seats: [],
  statusById: {},
  frame: 0,
  totalFrames: 0,
  videoFps: null,
  videoTs: null,
  fps: 0,
  inferenceMs: null,
  occupied: 0,
  calibration: { frame: 0, total: 0, meta: null },
  transitions: [],
  timeline: [],
  summary: null,
  error: null,
  sourceFilename: null,
  updatedAt: 0,
  pulse: {},
});

let state = { connection: "idle", cameras: {} };
const listeners = new Set();
let socket = null;
let retry = 0;
let retryTimer = null;
let refCount = 0;

function emit() {
  for (const l of listeners) l();
}

function patchCamera(cameraId, fn) {
  if (!cameraId) return;
  const prev = state.cameras[cameraId] || emptyCamera();
  const next = { ...prev, ...fn(prev), updatedAt: Date.now() };
  state = { ...state, cameras: { ...state.cameras, [cameraId]: next } };
  emit();
}

function seatsFrom(list, prevStatus = {}) {
  const seats = (list || []).map((s) => ({
    seat_id: s.seat_id || s.label,
    label: s.label ?? s.seat_label,
    status: s.status || prevStatus[s.seat_id] || "VACANT",
    bbox: s.bbox || null,
    confidence: s.confidence ?? null,
  }));
  const statusById = Object.fromEntries(seats.map((s) => [s.seat_id, s.status]));
  return { seats, statusById };
}

function applyStatuses(prev, list) {
  if (!list?.length) return {};
  const statusById = { ...prev.statusById };
  let changed = false;
  for (const s of list) {
    const id = s.seat_id || s.label;
    if (statusById[id] !== s.status) {
      statusById[id] = s.status;
      changed = true;
    }
  }
  if (!changed) return {};
  const seats = prev.seats.length
    ? prev.seats.map((s) => (statusById[s.seat_id] !== s.status ? { ...s, status: statusById[s.seat_id] } : s))
    : list.map((s) => ({ seat_id: s.seat_id || s.label, label: s.label, status: s.status, bbox: null }));
  return { seats, statusById };
}

/** Seed a camera from the REST snapshot (used on first load and after reconnects). */
export function hydrateCamera(snapshot) {
  if (!snapshot?.camera_id) return;
  patchCamera(snapshot.camera_id, (prev) => {
    if (!snapshot.live) {
      return { ...emptyCamera(), lastSession: snapshot.last_session || null };
    }
    const { seats, statusById } = seatsFrom(snapshot.seats);
    return {
      status: snapshot.status,
      stage: snapshot.stage,
      sessionId: snapshot.session_id,
      demo: !!snapshot.demo,
      frameW: snapshot.frame_w,
      frameH: snapshot.frame_h,
      seats,
      statusById,
      frame: snapshot.frame || 0,
      totalFrames: snapshot.total_frames || 0,
      videoFps: snapshot.video_fps,
      fps: snapshot.fps || 0,
      inferenceMs: snapshot.inference_ms,
      calibration: snapshot.calibration || prev.calibration,
      transitions: snapshot.recent_transitions || [],
      summary: snapshot.summary || null,
      error: snapshot.error || null,
      sourceFilename: snapshot.source_filename || null,
      occupied: seats.filter((s) => s.status === "OCCUPIED").length,
      timeline: prev.sessionId === snapshot.session_id ? prev.timeline : [],
    };
  });
}

/** Clear a camera's live state before a new upload starts. */
export function resetCamera(cameraId, patch = {}) {
  patchCamera(cameraId, () => ({ ...emptyCamera(), ...patch }));
}

function handle(msg) {
  const id = msg.camera_id;
  switch (msg.type) {
    case "ping":
      return;
    case "state_sync":
      hydrateCamera({ ...msg, live: true });
      return;
    case "init_progress":
      patchCamera(id, (prev) => ({
        status: "PROCESSING",
        stage: "CALIBRATING",
        sessionId: msg.session_id || prev.sessionId,
        calibration: { ...prev.calibration, frame: msg.frame || 0, total: msg.total || 0 },
      }));
      return;
    case "status_update":
      patchCamera(id, (prev) => ({
        status: msg.status,
        stage: msg.stage || prev.stage,
        sessionId: msg.session_id || prev.sessionId,
        demo: !!msg.demo,
        ...(prev.sessionId && msg.session_id && prev.sessionId !== msg.session_id
          ? { timeline: [], transitions: [], summary: null, error: null }
          : {}),
      }));
      return;
    case "seat_layout":
      patchCamera(id, (prev) => {
        const { seats, statusById } = seatsFrom(msg.seats, prev.statusById);
        return {
          seats,
          statusById,
          frameW: msg.frame_w ?? prev.frameW,
          frameH: msg.frame_h ?? prev.frameH,
          sessionId: msg.session_id || prev.sessionId,
          demo: !!msg.demo,
          occupied: seats.filter((s) => s.status === "OCCUPIED").length,
        };
      });
      return;
    case "seat_matrix":
      patchCamera(id, (prev) => {
        const patch = applyStatuses(prev, msg.seats);
        const seats = patch.seats || prev.seats;
        return { ...patch, demo: !!msg.demo, status: prev.status === "IDLE" ? "SIMULATING" : prev.status, occupied: seats.filter((s) => s.status === "OCCUPIED").length };
      });
      return;
    case "processing_update":
      patchCamera(id, (prev) => {
        const patch = applyStatuses(prev, msg.seats);
        const timeline =
          msg.video_ts !== undefined
            ? [...prev.timeline, { t: msg.video_ts, occupied: msg.occupied ?? 0 }].slice(-MAX_TIMELINE)
            : prev.timeline;
        return {
          ...patch,
          status: prev.status === "PROCESSING" ? "ANALYZING" : prev.status,
          stage: "TRACKING",
          sessionId: msg.session_id || prev.sessionId,
          frame: msg.frame || 0,
          totalFrames: msg.total_frames || prev.totalFrames,
          videoFps: msg.video_fps || prev.videoFps,
          videoTs: msg.video_ts ?? prev.videoTs,
          fps: msg.fps || 0,
          inferenceMs: msg.inference_ms ?? prev.inferenceMs,
          occupied: msg.occupied ?? prev.occupied,
          timeline,
        };
      });
      return;
    case "seat_transition":
      patchCamera(id, (prev) => {
        const item = {
          seat_id: msg.seat_id,
          label: msg.label,
          from: msg.from,
          to: msg.to,
          video_ts: msg.video_ts,
          at: msg.at,
          session_id: msg.session_id,
          demo: !!msg.demo,
        };
        const statusById = { ...prev.statusById, [msg.seat_id]: msg.to };
        return {
          statusById,
          seats: prev.seats.map((s) => (s.seat_id === msg.seat_id ? { ...s, status: msg.to } : s)),
          transitions: [item, ...prev.transitions].slice(0, MAX_TRANSITIONS),
          pulse: { ...prev.pulse, [msg.seat_id]: Date.now() },
        };
      });
      return;
    case "session_summary":
      patchCamera(id, () => ({
        status: msg.status,
        stage: "DONE",
        summary: msg.summary || null,
        error: msg.error || null,
      }));
      return;
    default:
  }
}

function connect() {
  if (socket || !getAuthToken()) return;
  state = { ...state, connection: retry ? "reconnecting" : "connecting" };
  emit();
  const ws = new WebSocket(wsUrl("/api/v1/occupancy/ws"));
  socket = ws;
  ws.onopen = () => {
    retry = 0;
    state = { ...state, connection: "open" };
    emit();
  };
  ws.onmessage = (ev) => {
    try {
      handle(JSON.parse(ev.data));
    } catch {
      /* ignore malformed frames */
    }
  };
  ws.onclose = () => {
    socket = null;
    state = { ...state, connection: refCount > 0 ? "reconnecting" : "idle" };
    emit();
    if (refCount > 0) {
      const delay = Math.min(15000, 1000 * 2 ** retry++);
      retryTimer = setTimeout(connect, delay);
    }
  };
  ws.onerror = () => ws.close();
}

function disconnect() {
  clearTimeout(retryTimer);
  if (socket) {
    socket.onclose = null;
    socket.close();
    socket = null;
  }
  state = { ...state, connection: "idle" };
  emit();
}

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

const getState = () => state;

/** Keep the socket open while any component using it is mounted. */
export function useLiveConnection() {
  useEffect(() => {
    refCount += 1;
    connect();
    return () => {
      refCount -= 1;
      if (refCount === 0) disconnect();
    };
  }, []);
  return useSyncExternalStore(subscribe, () => state.connection);
}

export function useLiveSelector(selector) {
  return useSyncExternalStore(subscribe, () => selector(getState()));
}

const EMPTY = emptyCamera();

export function useCamera(cameraId) {
  return useLiveSelector((s) => (cameraId && s.cameras[cameraId]) || EMPTY);
}

export function useSeatStatus(cameraId, seatId) {
  return useLiveSelector((s) => s.cameras[cameraId]?.statusById[seatId] || "UNKNOWN");
}

export function useSeatPulse(cameraId, seatId) {
  return useLiveSelector((s) => s.cameras[cameraId]?.pulse?.[seatId] || 0);
}

/** All seats currently known across cameras — used by the ambient background. */
export function useLiveSeats() {
  return useLiveSelector((s) => {
    const cams = Object.values(s.cameras);
    return cams.find((c) => c.seats.length && c.status !== "IDLE") || EMPTY;
  });
}

export const liveStore = { getState, subscribe, hydrateCamera, resetCamera };
