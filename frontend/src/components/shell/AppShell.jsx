/**
 * Application frame: navigation rail (bottom bar on small screens), the
 * ambient background, the pointer companion and route transitions.
 */

import { Suspense, useEffect, useRef, useState } from "react";
import { NavLink, useLocation, useOutlet } from "react-router-dom";
import { motion, useAnimate, useReducedMotion } from "motion/react";
import AmbientField from "./AmbientField";
import Cursor from "./Cursor";
import Icon from "../ui/Icon";
import { Toggle } from "../ui";
import { useLiveConnection } from "../../lib/live/store";
import { useWorkspace } from "../../lib/workspace";
import { clearAuthToken } from "../../api/client";
import "./shell.css";

const NAV = [
  { to: "/", label: "Live", icon: "live", end: true, tagline: "What's happening in the workspace right now" },
  { to: "/explorer", label: "Explorer", icon: "explorer", tagline: "Every seat, where it is and who uses it" },
  { to: "/analytics", label: "Analytics", icon: "analytics", tagline: "What happened over time" },
  { to: "/recommendations", label: "Recommendations", short: "Advice", icon: "recommendations", tagline: "What the measurements suggest" },
  { to: "/insights", label: "Insights", icon: "insights", tagline: "How healthy the workspace is" },
];

function titleFor(path) {
  if (path.startsWith("/sessions")) return { label: "Session", tagline: "One processed video, in detail" };
  return NAV.find((n) => n.to === path) || NAV[0];
}

const EASE = [0.76, 0, 0.24, 1];
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * Shutter page transition: a panel rises over the page, shows where you're
 * going, swaps the page underneath, then lifts away while the new page's
 * sections rise into place. Rapid clicks collapse into one transition to the
 * latest destination. Reduced motion swaps instantly.
 */
function useShutterOutlet() {
  const location = useLocation();
  const outlet = useOutlet();
  const reduce = useReducedMotion();
  const [scope, animate] = useAnimate();
  const [shown, setShown] = useState(() => ({ key: location.pathname, el: outlet }));
  const [title, setTitle] = useState(() => titleFor(location.pathname));
  const [entering, setEntering] = useState(false);
  const pending = useRef(null);
  const busy = useRef(false);
  const shownKey = useRef(location.pathname);

  const run = async () => {
    busy.current = true;
    try {
      await play();
    } catch {
      // If an animation is interrupted, never leave the page covered.
      if (pending.current) {
        setShown(pending.current);
        shownKey.current = pending.current.key;
        pending.current = null;
      }
      setEntering(false);
    } finally {
      busy.current = false;
    }
    if (pending.current && pending.current.key !== shownKey.current) run();
  };

  const play = async () => {
    setTitle(titleFor(pending.current.key));
    animate(".shutter-copy", { opacity: [0, 1], y: [28, 0] }, { duration: 0.45, delay: 0.18, ease: [0.22, 1, 0.36, 1] });
    await animate(".shutter-panel", { y: ["100%", "0%"] }, { duration: 0.5, ease: EASE });

    const target = pending.current;
    pending.current = null;
    setTitle(titleFor(target.key));
    setEntering(false);
    setShown(target);
    shownKey.current = target.key;
    window.scrollTo(0, 0);
    await wait(160);

    setEntering(true);
    animate(".shutter-copy", { opacity: 0, y: -20 }, { duration: 0.25, ease: EASE });
    await animate(".shutter-panel", { y: ["0%", "-100%"] }, { duration: 0.6, ease: EASE });
    document.getElementById("main")?.focus({ preventScroll: true });
  };

  useEffect(() => {
    const key = location.pathname;
    if (key === shownKey.current && !busy.current) return;
    pending.current = { key, el: outlet };
    if (reduce) {
      setShown(pending.current);
      shownKey.current = key;
      pending.current = null;
      window.scrollTo(0, 0);
      return;
    }
    if (!busy.current) run();
    // The outlet element is captured per navigation on purpose.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  return { shown, title, entering, scope };
}

function Shutter({ scope, title }) {
  return (
    <div ref={scope} className="shutter" aria-hidden="true">
      <div className="shutter-panel">
        <div className="shutter-grid" />
        <div className="shutter-top">
          <Mark size={24} />
          <span className="shutter-brand">Workspace Monitor</span>
        </div>
        <div className="shutter-copy">
          <div className="shutter-title">{title.label}</div>
          <div className="shutter-tagline">{title.tagline}</div>
        </div>
      </div>
    </div>
  );
}

const CONNECTION_TEXT = {
  open: "Live link open",
  connecting: "Connecting",
  reconnecting: "Reconnecting",
  idle: "Offline",
};

export function Mark({ size = 28 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <path d="M2 8V3.5A1.5 1.5 0 0 1 3.5 2H8M20 2h4.5A1.5 1.5 0 0 1 26 3.5V8M26 20v4.5a1.5 1.5 0 0 1-1.5 1.5H20M8 26H3.5A1.5 1.5 0 0 1 2 24.5V20" stroke="var(--scan)" strokeWidth="1.8" strokeLinecap="round" />
      <rect x="8" y="9" width="5" height="4" rx="1" fill="var(--available)" />
      <rect x="15" y="9" width="5" height="4" rx="1" fill="var(--occupied)" />
      <rect x="8" y="15" width="5" height="4" rx="1" fill="var(--occupied)" />
      <rect x="15" y="15" width="5" height="4" rx="1" fill="none" stroke="var(--available)" strokeWidth="1.4" />
    </svg>
  );
}

export default function AppShell() {
  const reduce = useReducedMotion();
  const { shown, title, entering, scope } = useShutterOutlet();
  const connection = useLiveConnection();
  const ws = useWorkspace();
  const user = (() => {
    try {
      return localStorage.getItem("user_name") || "Signed in";
    } catch {
      return "Signed in";
    }
  })();

  const signOut = () => {
    clearAuthToken();
    window.dispatchEvent(new Event("auth:expired"));
  };

  return (
    <div className="shell">
      <AmbientField />
      <Cursor />
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <aside className="rail" aria-label="Primary">
        <div className="rail-brand">
          <Mark />
          <div>
            <div className="rail-name">Workspace Monitor</div>
            <div className="rail-tag">Seat-level occupancy from camera video</div>
          </div>
        </div>

        <nav className="rail-nav">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className="rail-link">
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.span
                      layoutId="rail-active"
                      className="rail-active"
                      transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 36 }}
                    />
                  )}
                  <Icon name={item.icon} />
                  <span>{item.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="rail-foot">
          <div className="rail-status" role="status">
            <span className={`dot ${connection === "open" ? "dot-live" : "dot-unknown"}`} />
            {CONNECTION_TEXT[connection] || connection}
          </div>
          {(ws.demoDataPresent || ws.demoMode) && (
            <Toggle checked={ws.includeDemo} onChange={ws.setIncludeDemo}>
              Include demo data
            </Toggle>
          )}
          <div className="rail-user">
            <span className="small">{user}</span>
            <button type="button" className="btn btn-ghost btn-sm" onClick={signOut}>
              <Icon name="logout" /> Sign out
            </button>
          </div>
        </div>
      </aside>

      <header className="topbar">
        <div className="row">
          <Mark size={24} />
          <span className="rail-name">Workspace Monitor</span>
        </div>
        <div className="row small muted">
          <span className={`dot ${connection === "open" ? "dot-live" : "dot-unknown"}`} />
          {connection === "open" ? "Live" : CONNECTION_TEXT[connection]}
        </div>
      </header>

      <main id="main" className="main" tabIndex={-1}>
        <div key={shown.key} className={`page-wrap${entering ? " is-entering" : ""}`}>
          {/* Lazy pages suspend here, inside the page, so the shell and its transition never unmount. */}
          <Suspense fallback={<div className="page" />}>{shown.el}</Suspense>
        </div>
      </main>

      <Shutter scope={scope} title={title} />

      <nav className="tabbar" aria-label="Primary">
        {NAV.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end} className="tab-link">
            <Icon name={item.icon} size={20} />
            <span>{item.short || item.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
