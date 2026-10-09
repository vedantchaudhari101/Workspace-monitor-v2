/**
 * Living background: an office floor seen from a ceiling camera.
 *
 * A perspective line drawing of a workspace — desk clusters with monitors and
 * chairs, a glass meeting room, a lounge, plants — that the system is
 * "watching". Small figures walk in, sit down, work for a while and leave; a
 * mounted camera sweeps the room with its view cone and briefly frames people
 * it sees sit down.
 *
 * Honesty rule: the decorative figures and chairs only ever use the neutral /
 * cyan accent. Red and green appear only while a real video is being analysed,
 * when the first chairs of the plan take the live status of the detected
 * seats (and the decorative people stop using those chairs).
 *
 * Canvas 2D, ~30 fps, paused in hidden tabs, drawn once under reduced motion.
 */

import { useEffect, useRef } from "react";
import { useReducedMotion } from "motion/react";
import { useLiveSeats } from "../../lib/live/store";

const INK = [214, 226, 236];
const SCAN = [127, 219, 240];
const OCC = [255, 90, 95];
const AVAIL = [46, 212, 122];

const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
const rand = (a, b) => a + Math.random() * (b - a);

// ── Office layout (world units ≈ metres; x right, y up, z away) ─────────────

const ROOM = { x0: -9, x1: 9, z0: 3, z1: 19, h: 3 };
const DESK = { w: 1.4, d: 0.75, h: 0.74 };
const AISLE_Z = [4.2, 8.6, 12.8];
const DOOR = { x: -1.2, z: 3 };

function buildLayout() {
  const desks = [];
  const chairs = [];
  const monitors = [];

  // Bench clusters: two desks side by side, mirrored across a spine.
  const clusterOrigins = [];
  for (const cz of [6.2, 10.6]) {
    for (const cx of [-7.2, -3.8, -0.4]) clusterOrigins.push([cx, cz]);
  }
  clusterOrigins.push([3.0, 6.2], [6.4, 6.2]);

  for (const [cx, cz] of clusterOrigins) {
    for (let col = 0; col < 2; col++) {
      for (const side of [-1, 1]) {
        const x0 = cx + col * DESK.w;
        const z0 = side < 0 ? cz - DESK.d : cz;
        desks.push({ x0, x1: x0 + DESK.w - 0.04, z0, z1: z0 + DESK.d });
        const mx = x0 + DESK.w / 2;
        const mz = side < 0 ? cz - 0.12 : cz + 0.12;
        monitors.push({ x: mx, z: mz, face: side });
        const chairZ = side < 0 ? z0 - 0.45 : z0 + DESK.d + 0.45;
        chairs.push({ x: mx, z: chairZ, back: side, aisleZ: side < 0 ? cz - 1.6 : cz + 1.6 });
      }
    }
  }

  // Meeting room (glass) in the back-right corner, table and chairs.
  const meeting = { x0: 3.6, x1: 9, z0: 12.4, z1: 19 };
  const table = { x0: 5.0, x1: 7.8, z0: 15.0, z1: 16.6 };
  for (let i = 0; i < 3; i++) {
    const x = table.x0 + 0.5 + i * 0.9;
    chairs.push({ x, z: table.z0 - 0.5, back: -1, aisleZ: 13.6, meeting: true });
    chairs.push({ x, z: table.z1 + 0.5, back: 1, aisleZ: 13.6, meeting: true });
  }

  const lounge = { sofa: { x0: -8.4, x1: -5.6, z0: 16.8, z1: 17.6 }, table: { x0: -7.6, x1: -6.4, z0: 15.4, z1: 16.1 } };
  const plants = [
    [-8.5, 3.5], [8.5, 3.5], [-8.5, 14.2], [2.9, 18.4], [-4.6, 18.4], [8.4, 11.6],
  ];
  const camera = { x: -8.7, y: 2.75, z: 18.7 };

  return { desks, chairs, monitors, meeting, table, lounge, plants, camera };
}

// ── People ──────────────────────────────────────────────────────────────────

function routeTo(from, chair) {
  // Walk along the aisle in front of the chair, then step into it.
  return [
    { x: from.x, z: chair.aisleZ },
    { x: chair.x, z: chair.aisleZ },
    { x: chair.x, z: chair.z },
  ];
}

function makePerson(layout, reserved) {
  return {
    x: DOOR.x,
    z: DOOR.z - 0.2,
    path: [],
    state: "idle",
    chair: null,
    wait: rand(0, 6),
    speed: rand(1.1, 1.5),
    phase: Math.random() * Math.PI * 2,
    seenAt: 0,
    layout,
    reserved,
  };
}

function freeChair(layout, people, reserved) {
  const taken = new Set(people.map((p) => p.chair).filter(Boolean));
  const options = layout.chairs.filter((c, i) => !taken.has(c) && !reserved.has(i));
  return options.length ? options[Math.floor(Math.random() * options.length)] : null;
}

function stepPerson(p, dt, people, t) {
  if (p.state === "idle") {
    p.wait -= dt;
    if (p.wait <= 0) {
      const chair = freeChair(p.layout, people, p.reserved.current);
      if (chair) {
        p.chair = chair;
        p.path = [{ x: DOOR.x, z: AISLE_Z[0] }, ...routeTo({ x: DOOR.x, z: AISLE_Z[0] }, chair)];
        p.state = "walking";
      } else {
        p.wait = rand(2, 5);
      }
    }
    return;
  }

  if (p.state === "sitting") {
    p.wait -= dt;
    if (p.wait <= 0) {
      // Leave: back to the aisle, then either another chair or out of the door.
      const exit = Math.random() < 0.35;
      const next = exit ? null : freeChair(p.layout, people.filter((q) => q !== p), p.reserved.current);
      const from = { x: p.chair.x, z: p.chair.aisleZ };
      p.path = [from];
      if (next) {
        p.path.push(...routeTo(from, next));
        p.chair = next;
        p.state = "walking";
      } else {
        p.path.push({ x: from.x, z: AISLE_Z[0] }, { x: DOOR.x, z: AISLE_Z[0] }, { x: DOOR.x, z: DOOR.z - 0.4 });
        p.chair = null;
        p.state = "leaving";
      }
    }
    return;
  }

  // walking / leaving
  const target = p.path[0];
  if (!target) {
    if (p.state === "walking" && p.chair) {
      p.state = "sitting";
      p.wait = rand(8, 26);
      p.seenAt = t;
    } else {
      p.state = "idle";
      p.wait = rand(3, 10);
    }
    return;
  }
  const dx = target.x - p.x;
  const dz = target.z - p.z;
  const dist = Math.hypot(dx, dz);
  const step = p.speed * dt;
  if (dist <= step) {
    p.x = target.x;
    p.z = target.z;
    p.path.shift();
  } else {
    p.x += (dx / dist) * step;
    p.z += (dz / dist) * step;
  }
}

// ── Component ───────────────────────────────────────────────────────────────

export default function AmbientField() {
  const canvasRef = useRef(null);
  const reduce = useReducedMotion();
  const live = useLiveSeats();
  const liveRef = useRef({ statuses: [], active: false });
  const reservedRef = useRef(new Set());

  // Real seats → the first chairs of the plan, ordered left to right as the camera sees them.
  useEffect(() => {
    const active = live.status === "ANALYZING" && !live.demo && live.seats.length > 0;
    const ordered = [...live.seats]
      .filter((s) => s.bbox)
      .sort((a, b) => a.bbox.x1 - b.bbox.x1)
      .map((s) => live.statusById[s.seat_id] || s.status);
    liveRef.current = { active, statuses: active ? ordered : [] };
    reservedRef.current = new Set(active ? ordered.map((_, i) => i) : []);
  }, [live]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const ctx = canvas.getContext("2d");
    const layout = buildLayout();
    const people = Array.from({ length: 9 }, () => makePerson(layout, reservedRef));

    let w = 0;
    let h = 0;
    let raf = 0;
    let last = 0;
    let t = 0;
    const pointer = { x: 0, y: 0, tx: 0, ty: 0 };

    // Camera: positioned above the front of the room, tilted down.
    const cam = { H: 13, pitch: 0.9, f: 1, cx: 0, cy: 0, x: 0 };
    const cosP = () => Math.cos(cam.pitch);
    const sinP = () => Math.sin(cam.pitch);

    const project = (x, y, z) => {
      const X = x - cam.x;
      const Y = y - cam.H;
      const Z = z + 5;
      const yc = Y * cosP() + Z * sinP();
      const zc = -Y * sinP() + Z * cosP();
      if (zc < 0.1) return null;
      return { x: cam.cx + (X / zc) * cam.f, y: cam.cy - (yc / zc) * cam.f, d: zc };
    };

    const fade = (z) => Math.max(0, Math.min(1, 1.25 - (z - ROOM.z0) / (ROOM.z1 - ROOM.z0)));

    const line = (pts, color, width = 1) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.beginPath();
      let started = false;
      for (const [x, y, z] of pts) {
        const p = project(x, y, z);
        if (!p) continue;
        if (!started) {
          ctx.moveTo(p.x, p.y);
          started = true;
        } else ctx.lineTo(p.x, p.y);
      }
      ctx.stroke();
    };

    const poly = (pts, fill, stroke) => {
      ctx.beginPath();
      pts.forEach(([x, y, z], i) => {
        const p = project(x, y, z);
        if (!p) return;
        if (i === 0) ctx.moveTo(p.x, p.y);
        else ctx.lineTo(p.x, p.y);
      });
      ctx.closePath();
      if (fill) {
        ctx.fillStyle = fill;
        ctx.fill();
      }
      if (stroke) {
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    };

    // Box with a filled top face and vertical edges.
    const box = (x0, x1, z0, z1, y0, y1, alpha, fillAlpha = alpha * 0.35, color = INK) => {
      const top = [[x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]];
      poly(top, rgba(color, fillAlpha), rgba(color, alpha));
      ctx.strokeStyle = rgba(color, alpha * 0.7);
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (const [x, z] of [[x0, z0], [x1, z0], [x1, z1], [x0, z1]]) {
        const a = project(x, y0, z);
        const b = project(x, y1, z);
        if (!a || !b) continue;
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
      }
      ctx.stroke();
    };

    const drawChair = (c, alpha, tint = null, fillA = 0) => {
      const s = 0.24;
      const col = tint || INK;
      box(c.x - s, c.x + s, c.z - s, c.z + s, 0.0, 0.46, alpha, fillA || alpha * 0.25, col);
      // backrest on the side away from the desk
      const bz = c.back < 0 ? c.z - s : c.z + s;
      poly([[c.x - s, 0.46, bz], [c.x + s, 0.46, bz], [c.x + s, 0.95, bz], [c.x - s, 0.95, bz]], rgba(col, (fillA || alpha * 0.25) * 0.8), rgba(col, alpha));
    };

    // People are drawn upright in screen space (a vertical body and a head),
    // sized by their depth, so they read as people rather than leaning sticks.
    const drawPerson = (p, sitting, alpha) => {
      const foot = project(p.x, 0, p.z);
      if (!foot) return null;
      const s = (cam.f / foot.d) * 0.72; // pixels per metre, foreshortened
      const bob = sitting ? 0 : Math.abs(Math.sin(t * 7 + p.phase)) * 0.05 * s;
      const hip = foot.y - (sitting ? 0.5 : 0.85) * s - bob;
      const neck = foot.y - (sitting ? 1.15 : 1.5) * s - bob;
      const r = Math.max(1.6, 0.13 * s);
      const head = { x: foot.x, y: neck - r * 1.25 };

      // floor shadow
      ctx.fillStyle = rgba(SCAN, alpha * 0.14);
      ctx.beginPath();
      ctx.ellipse(foot.x, foot.y, r * 2.4, r * 0.9, 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = rgba(SCAN, alpha);
      ctx.lineCap = "round";
      ctx.lineWidth = Math.max(1.4, r * 1.25);
      ctx.beginPath();
      ctx.moveTo(foot.x, neck);
      ctx.lineTo(foot.x, hip);
      ctx.stroke();
      // legs: walking stride, or bent forward when seated
      ctx.lineWidth = Math.max(1, r * 0.6);
      ctx.beginPath();
      if (sitting) {
        const dir = p.chair && p.chair.back < 0 ? 1 : -1;
        ctx.moveTo(foot.x, hip);
        ctx.lineTo(foot.x + dir * r * 0.6, hip + r * 0.4);
        ctx.lineTo(foot.x + dir * r * 0.6, foot.y);
      } else {
        const stride = Math.sin(t * 7 + p.phase) * r * 0.9;
        ctx.moveTo(foot.x, hip);
        ctx.lineTo(foot.x + stride, foot.y);
        ctx.moveTo(foot.x, hip);
        ctx.lineTo(foot.x - stride, foot.y);
      }
      ctx.stroke();
      ctx.lineCap = "butt";

      ctx.fillStyle = rgba(SCAN, alpha);
      ctx.beginPath();
      ctx.arc(head.x, head.y, r, 0, Math.PI * 2);
      ctx.fill();
      return { head, base: foot };
    };

    const brackets = (x0, y0, x1, y1, alpha) => {
      const k = Math.min(10, (x1 - x0) / 3);
      ctx.strokeStyle = rgba(SCAN, alpha);
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      for (const [cx, cy, sx, sy] of [[x0, y0, 1, 1], [x1, y0, -1, 1], [x0, y1, 1, -1], [x1, y1, -1, -1]]) {
        ctx.moveTo(cx, cy + sy * k);
        ctx.lineTo(cx, cy);
        ctx.lineTo(cx + sx * k, cy);
      }
      ctx.stroke();
    };

    const resize = () => {
      const dpr = Math.min(1.5, window.devicePixelRatio || 1);
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const narrow = w < 900;
      // Fit the room's front edge to roughly the content width, centred low on the page.
      cam.f = narrow ? Math.min(w * 0.95, h * 0.8) : Math.min(w * 0.68, h * 1.1);
      cam.baseCx = narrow ? w * 0.5 : w * 0.58;
      cam.baseCy = h * (narrow ? 0.62 : 0.6) + 0.155 * cam.f;
    };

    const onMove = (e) => {
      pointer.tx = e.clientX / w - 0.5;
      pointer.ty = e.clientY / h - 0.5;
    };

    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      pointer.x += (pointer.tx - pointer.x) * 0.05;
      pointer.y += (pointer.ty - pointer.y) * 0.05;
      cam.x = pointer.x * 1.4;
      cam.pitch = 0.9 + pointer.y * 0.04;
      cam.cx = cam.baseCx;
      cam.cy = cam.baseCy;

      const { desks, chairs, monitors, meeting, table, lounge, plants, camera } = layout;
      const { active, statuses } = liveRef.current;

      // Floor tiles
      for (let x = ROOM.x0; x <= ROOM.x1; x += 1) {
        line([[x, 0, ROOM.z0], [x, 0, ROOM.z1]], rgba(INK, 0.035));
      }
      for (let z = ROOM.z0; z <= ROOM.z1; z += 1) {
        line([[ROOM.x0, 0, z], [ROOM.x1, 0, z]], rgba(INK, 0.035 * fade(z) + 0.01));
      }
      // Room outline and walls (back and left solid, glass suggested by verticals)
      poly([[ROOM.x0, 0, ROOM.z0], [ROOM.x1, 0, ROOM.z0], [ROOM.x1, 0, ROOM.z1], [ROOM.x0, 0, ROOM.z1]], null, rgba(INK, 0.12));
      for (const [ax, az, bx, bz] of [[ROOM.x0, ROOM.z1, ROOM.x1, ROOM.z1], [ROOM.x0, ROOM.z0, ROOM.x0, ROOM.z1], [ROOM.x1, ROOM.z0, ROOM.x1, ROOM.z1]]) {
        poly([[ax, 0, az], [bx, 0, bz], [bx, ROOM.h, bz], [ax, ROOM.h, az]], rgba(INK, 0.018), rgba(INK, 0.08));
      }
      // Windows along the right wall
      for (let z = ROOM.z0 + 1; z < ROOM.z1 - 1; z += 2.2) {
        poly([[ROOM.x1, 1.0, z], [ROOM.x1, 1.0, z + 1.6], [ROOM.x1, 2.4, z + 1.6], [ROOM.x1, 2.4, z]], rgba(SCAN, 0.025), rgba(SCAN, 0.08));
      }
      // Door gap at the front wall
      line([[DOOR.x - 0.6, 0, DOOR.z], [DOOR.x - 0.6, 2.1, DOOR.z], [DOOR.x + 0.6, 2.1, DOOR.z], [DOOR.x + 0.6, 0, DOOR.z]], rgba(INK, 0.14));

      // Meeting room glass walls
      for (const [ax, az, bx, bz] of [[meeting.x0, meeting.z0, meeting.x0, meeting.z1], [meeting.x0, meeting.z0, meeting.x1, meeting.z0]]) {
        const steps = Math.round(Math.hypot(bx - ax, bz - az) / 0.9);
        poly([[ax, 0, az], [bx, 0, bz], [bx, 2.6, bz], [ax, 2.6, az]], rgba(SCAN, 0.022), rgba(SCAN, 0.1));
        for (let i = 1; i < steps; i++) {
          const k = i / steps;
          const x = ax + (bx - ax) * k;
          const z = az + (bz - az) * k;
          if (Math.abs(x - 3.6) < 0.01 && z > 13.2 && z < 14.4) continue; // door
          line([[x, 0, z], [x, 2.6, z]], rgba(SCAN, 0.05));
        }
      }
      box(table.x0, table.x1, table.z0, table.z1, 0, 0.74, 0.16, 0.05);

      // Lounge
      box(lounge.sofa.x0, lounge.sofa.x1, lounge.sofa.z0, lounge.sofa.z1, 0, 0.42, 0.14, 0.05);
      box(lounge.sofa.x0, lounge.sofa.x1, lounge.sofa.z1 - 0.18, lounge.sofa.z1, 0.42, 0.85, 0.12, 0.04);
      box(lounge.table.x0, lounge.table.x1, lounge.table.z0, lounge.table.z1, 0, 0.38, 0.12, 0.04);

      // Desks and monitors
      for (const d of desks) {
        const a = 0.1 + 0.12 * fade((d.z0 + d.z1) / 2);
        box(d.x0, d.x1, d.z0, d.z1, 0, DESK.h, a, a * 0.3);
      }
      for (const m of monitors) {
        const a = 0.12 + 0.14 * fade(m.z);
        poly([[m.x - 0.28, 0.82, m.z], [m.x + 0.28, 0.82, m.z], [m.x + 0.28, 1.16, m.z], [m.x - 0.28, 1.16, m.z]], rgba(SCAN, a * 0.35), rgba(INK, a));
        line([[m.x, DESK.h, m.z], [m.x, 0.82, m.z]], rgba(INK, a * 0.8));
      }

      // Chairs — first ones carry real live status while a video is analysed
      const seated = new Set(people.filter((p) => p.state === "sitting").map((p) => p.chair));
      chairs.forEach((c, i) => {
        const a = 0.12 + 0.14 * fade(c.z);
        if (active && i < statuses.length) {
          const s = statuses[i];
          const col = s === "OCCUPIED" ? OCC : s === "VACANT" ? AVAIL : INK;
          drawChair(c, 0.55, col, 0.22);
        } else if (seated.has(c)) {
          drawChair(c, a + 0.1, SCAN, 0.12);
        } else {
          drawChair(c, a);
        }
      });

      // Plants
      for (const [px, pz] of plants) {
        const a = 0.12 + 0.12 * fade(pz);
        box(px - 0.2, px + 0.2, pz - 0.2, pz + 0.2, 0, 0.42, a, a * 0.3);
        for (let k = 0; k < 7; k++) {
          const ang = (k / 7) * Math.PI * 2 + 0.4;
          const sway = Math.sin(t * 0.8 + k + px) * 0.04;
          line([[px, 0.42, pz], [px + Math.cos(ang) * 0.32 + sway, 1.05, pz + Math.sin(ang) * 0.32]], rgba(AVAIL, a * 0.9));
        }
      }

      // People
      const drawn = [];
      for (const p of people) {
        if (p.state === "idle") continue;
        const sitting = p.state === "sitting";
        const r = drawPerson(p, sitting, 0.4 + 0.35 * fade(p.z));
        if (r) drawn.push({ p, ...r });
      }

      // Ceiling camera and its sweeping view cone
      const sweep = Math.sin(t * 0.35) * 0.55;
      const dir = Math.PI * 0.12 + sweep; // angle from +x axis towards -z
      const reach = 13;
      const spread = 0.32;
      const fl = [
        [camera.x + Math.cos(dir - spread) * reach, 0, camera.z - Math.sin(dir - spread) * reach],
        [camera.x + Math.cos(dir + spread) * reach, 0, camera.z - Math.sin(dir + spread) * reach],
      ];
      const camP = project(camera.x, camera.y, camera.z);
      const a1 = project(...fl[0]);
      const a2 = project(...fl[1]);
      if (camP && a1 && a2) {
        const g = ctx.createLinearGradient(camP.x, camP.y, (a1.x + a2.x) / 2, (a1.y + a2.y) / 2);
        g.addColorStop(0, rgba(SCAN, 0.09));
        g.addColorStop(1, rgba(SCAN, 0));
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.moveTo(camP.x, camP.y);
        ctx.lineTo(a1.x, a1.y);
        ctx.lineTo(a2.x, a2.y);
        ctx.closePath();
        ctx.fill();
        box(camera.x - 0.15, camera.x + 0.15, camera.z - 0.25, camera.z + 0.05, camera.y - 0.15, camera.y + 0.05, 0.5, 0.2, SCAN);
        ctx.fillStyle = rgba(OCC, 0.5 + 0.5 * Math.sin(t * 3));
        ctx.beginPath();
        ctx.arc(camP.x, camP.y - 2, 1.6, 0, Math.PI * 2);
        ctx.fill();
      }

      // Detection brackets: briefly frame people who just sat down, or who are in the cone.
      const inCone = (x, z) => {
        const ang = Math.atan2(-(z - camera.z), x - camera.x);
        return Math.abs(ang - dir) < spread && Math.hypot(x - camera.x, z - camera.z) < reach;
      };
      for (const d of drawn) {
        const since = t - d.p.seenAt;
        const fresh = d.p.state === "sitting" && since < 2.2;
        if (!fresh && !inCone(d.p.x, d.p.z)) continue;
        const r = Math.abs(d.base.y - d.head.y);
        const half = Math.max(6, r * 0.45);
        const alpha = fresh ? 0.75 * (1 - since / 2.2) + 0.15 : 0.35;
        brackets(d.head.x - half, d.head.y - half * 0.8, d.head.x + half, d.base.y + 2, alpha);
      }
    };

    const tick = (dt) => {
      t += dt;
      for (const p of people) stepPerson(p, dt, people, t);
    };

    const loop = (now) => {
      raf = requestAnimationFrame(loop);
      if (document.visibilityState !== "visible") {
        last = now;
        return;
      }
      if (now - last < 33) return;
      const dt = Math.min(0.1, (now - last) / 1000 || 0.033);
      last = now;
      tick(dt);
      draw();
    };

    resize();
    window.addEventListener("resize", resize);
    if (reduce) {
      // A calm still frame: a few people already at their desks.
      for (const p of people.slice(0, 5)) {
        const chair = freeChair(layout, people, reservedRef.current);
        if (!chair) break;
        p.chair = chair;
        p.x = chair.x;
        p.z = chair.z;
        p.state = "sitting";
        p.wait = 1e9;
        p.seenAt = -10;
      }
      t = 10;
      draw();
    } else {
      // Warm up so the room is already populated on first paint.
      for (let i = 0; i < 400; i++) tick(0.1);
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
