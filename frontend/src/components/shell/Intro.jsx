/**
 * One-time intro: shown on the first load of a visit, then never again until
 * the tab is closed. Skipped entirely under reduced motion.
 */

import { useEffect, useRef, useState } from "react";
import { animate, motion, useReducedMotion } from "motion/react";
import { Mark } from "./AppShell";
import "./shell.css";

const KEY = "wm.introShown";

function alreadyShown() {
  try {
    return sessionStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export default function Intro() {
  const reduce = useReducedMotion();
  const [visible, setVisible] = useState(() => !alreadyShown());
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const bar = useRef(null);

  useEffect(() => {
    if (!visible) return undefined;
    try {
      sessionStorage.setItem(KEY, "1");
    } catch {
      /* ignore */
    }
    if (reduce) {
      setVisible(false);
      return undefined;
    }
    let cancelled = false;
    const counter = animate(0, 100, {
      duration: 1.1,
      ease: [0.65, 0, 0.35, 1],
      onUpdate: (v) => {
        setCount(Math.round(v));
        if (bar.current) bar.current.style.transform = `scaleX(${v / 100})`;
      },
    });
    counter.then(async () => {
      if (cancelled || !ref.current) return;
      await animate(ref.current, { y: ["0%", "-100%"] }, { duration: 0.7, ease: [0.76, 0, 0.24, 1] });
      if (!cancelled) setVisible(false);
    });
    return () => {
      cancelled = true;
      counter.stop();
    };
  }, [visible, reduce]);

  if (!visible || reduce) return null;
  return (
    <motion.div ref={ref} className="intro" aria-hidden="true">
      <div className="intro-top">
        <Mark size={28} />
        <span>Workspace Monitor</span>
      </div>
      <div className="intro-bottom">
        <span className="intro-label">Calibrating workspace</span>
        <span className="intro-count">{String(count).padStart(3, "0")}</span>
      </div>
      <div className="intro-track">
        <span ref={bar} style={{ transform: "scaleX(0)" }} />
      </div>
    </motion.div>
  );
}
