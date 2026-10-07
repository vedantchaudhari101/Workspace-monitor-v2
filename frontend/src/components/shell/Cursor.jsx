/**
 * Pointer companion: a soft light that follows the cursor across the dark
 * surface, and a ring that tightens around interactive targets.
 * The native cursor stays visible. Disabled on touch and reduced motion.
 */

import { useEffect, useRef } from "react";
import { useReducedMotion } from "motion/react";

const INTERACTIVE = "a, button, [role='button'], input, select, textarea, label, [data-cursor]";

export default function Cursor() {
  const ringRef = useRef(null);
  const glowRef = useRef(null);
  const reduce = useReducedMotion();

  useEffect(() => {
    const fine = window.matchMedia("(pointer: fine)").matches;
    if (reduce || !fine) return undefined;
    const ring = ringRef.current;
    const glow = glowRef.current;
    const target = { x: -100, y: -100 };
    const pos = { x: -100, y: -100 };
    let scale = 1;
    let targetScale = 1;
    let visible = false;
    let raf = 0;

    const onMove = (e) => {
      target.x = e.clientX;
      target.y = e.clientY;
      const hit = e.target.closest?.(INTERACTIVE);
      targetScale = hit ? 1.6 : 1;
      if (!visible) {
        visible = true;
        pos.x = target.x;
        pos.y = target.y;
        ring.style.opacity = "1";
        glow.style.opacity = "1";
      }
    };
    const onLeave = () => {
      visible = false;
      ring.style.opacity = "0";
      glow.style.opacity = "0";
    };
    const tick = () => {
      pos.x += (target.x - pos.x) * 0.22;
      pos.y += (target.y - pos.y) * 0.22;
      scale += (targetScale - scale) * 0.2;
      ring.style.transform = `translate3d(${pos.x - 14}px, ${pos.y - 14}px, 0) scale(${scale})`;
      glow.style.transform = `translate3d(${target.x - 220}px, ${target.y - 220}px, 0)`;
      raf = requestAnimationFrame(tick);
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("pointerleave", onLeave);
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerleave", onLeave);
    };
  }, [reduce]);

  if (reduce) return null;
  return (
    <>
      <div ref={glowRef} className="cursor-glow" aria-hidden="true" />
      <div ref={ringRef} className="cursor-ring" aria-hidden="true" />
    </>
  );
}
