/**
 * Living background: a perspective floor grid the system is "watching".
 *
 * - A slow scan plane sweeps the floor (the camera at work).
 * - The grid drifts toward the viewer and leans with the pointer.
 * - When a camera has a calibrated layout, its real seats appear as nodes on
 *   the floor at their actual positions, glowing red (occupied) or green
 *   (available). With no live data the floor stays empty — nothing invented.
 *
 * Canvas 2D, ~30 fps, paused in hidden tabs, drawn once under reduced motion.
 */

import { useEffect, useRef } from "react";
import { useReducedMotion } from "motion/react";
import { useLiveSeats } from "../../lib/live/store";

const SCAN = [127, 219, 240];
const OCC = [255, 90, 95];
const AVAIL = [46, 212, 122];

export default function AmbientField() {
  const canvasRef = useRef(null);
  const reduce = useReducedMotion();
  const live = useLiveSeats();
  const seatsRef = useRef([]);

  useEffect(() => {
    const fw = live.frameW;
    const fh = live.frameH;
    seatsRef.current =
      fw && fh
        ? live.seats
            .filter((s) => s.bbox)
            .map((s) => ({
              u: (s.bbox.x1 + s.bbox.x2) / 2 / fw,
              v: (s.bbox.y1 + s.bbox.y2) / 2 / fh,
              status: live.statusById[s.seat_id] || s.status,
            }))
        : [];
  }, [live]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const ctx = canvas.getContext("2d");
    let w = 0;
    let h = 0;
    let dpr = 1;
    let raf = 0;
    let last = 0;
    let t = 0;
    const pointer = { x: 0, y: 0, tx: 0, ty: 0 };

    const resize = () => {
      dpr = Math.min(1.5, window.devicePixelRatio || 1);
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const onMove = (e) => {
      pointer.tx = e.clientX / w - 0.5;
      pointer.ty = e.clientY / h - 0.5;
    };

    const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;

    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      pointer.x += (pointer.tx - pointer.x) * 0.04;
      pointer.y += (pointer.ty - pointer.y) * 0.04;

      const horizon = h * 0.34 + pointer.y * 18;
      const cx = w * 0.62 + pointer.x * 40;
      const floorH = h - horizon;
      const focal = floorH * 0.9;
      const camH = 1.0;
      const project = (x, z) => ({ x: cx + (x / z) * focal, y: horizon + (camH / z) * focal });

      // Depth lines (drifting towards the viewer).
      const spacing = 0.5;
      const drift = (t * 0.06) % spacing;
      for (let z = 12; z > 0.6; z -= spacing) {
        const zz = z - drift;
        if (zz < 0.6) continue;
        const a = project(-8, zz);
        const b = project(8, zz);
        const alpha = Math.max(0, 0.11 - zz * 0.008);
        ctx.strokeStyle = rgba(SCAN, alpha);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
      // Lines running away from the viewer.
      for (let x = -8; x <= 8; x += 0.5) {
        const near = project(x, 0.6);
        const far = project(x, 12);
        const grad = ctx.createLinearGradient(near.x, near.y, far.x, far.y);
        grad.addColorStop(0, rgba(SCAN, 0.08));
        grad.addColorStop(1, rgba(SCAN, 0));
        ctx.strokeStyle = grad;
        ctx.beginPath();
        ctx.moveTo(near.x, near.y);
        ctx.lineTo(far.x, far.y);
        ctx.stroke();
      }

      // Scan plane sweeping from far to near.
      const cycle = 9;
      const phase = (t % cycle) / cycle;
      const zScan = 12 - phase * 11.2;
      const sl = project(-8, zScan);
      const sr = project(8, zScan);
      const band = ctx.createLinearGradient(0, sl.y - 30, 0, sl.y + 2);
      band.addColorStop(0, rgba(SCAN, 0));
      band.addColorStop(1, rgba(SCAN, 0.07 * Math.sin(phase * Math.PI)));
      ctx.fillStyle = band;
      ctx.fillRect(0, sl.y - 30, w, 32);
      ctx.strokeStyle = rgba(SCAN, 0.22 * Math.sin(phase * Math.PI));
      ctx.beginPath();
      ctx.moveTo(sl.x, sl.y);
      ctx.lineTo(sr.x, sr.y);
      ctx.stroke();

      // Real seats from the active camera, laid on the floor.
      for (const s of seatsRef.current) {
        const wx = (s.u - 0.5) * 6;
        const wz = 1.6 + (1 - s.v) * 6;
        const p = project(wx, wz);
        const col = s.status === "OCCUPIED" ? OCC : s.status === "VACANT" ? AVAIL : SCAN;
        const r = Math.max(2, 9 / wz);
        const swept = Math.abs(wz - zScan) < 0.6 ? 0.35 : 0;
        const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 6);
        glow.addColorStop(0, rgba(col, 0.28 + swept));
        glow.addColorStop(1, rgba(col, 0));
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r * 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = rgba(col, 0.85);
        ctx.beginPath();
        ctx.ellipse(p.x, p.y, r, r * 0.55, 0, 0, Math.PI * 2);
        ctx.fill();
      }
    };

    const loop = (now) => {
      raf = requestAnimationFrame(loop);
      if (document.visibilityState !== "visible") return;
      if (now - last < 33) return;
      t += Math.min(0.1, (now - last) / 1000 || 0.033);
      last = now;
      draw();
    };

    resize();
    window.addEventListener("resize", resize);
    if (reduce) {
      draw();
    } else {
      window.addEventListener("pointermove", onMove, { passive: true });
      raf = requestAnimationFrame(loop);
    }
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onMove);
    };
  }, [reduce]);

  return <canvas ref={canvasRef} className="ambient-field" aria-hidden="true" />;
}
