/**
 * Application frame: navigation rail (bottom bar on small screens), the
 * ambient background, the pointer companion and route transitions.
 */

import { NavLink, useLocation, useOutlet } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import AmbientField from "./AmbientField";
import Cursor from "./Cursor";
import Icon from "../ui/Icon";
import { Toggle } from "../ui";
import { useLiveConnection } from "../../lib/live/store";
import { useWorkspace } from "../../lib/workspace";
import { clearAuthToken } from "../../api/client";
import "./shell.css";

const NAV = [
  { to: "/", label: "Live", icon: "live", end: true },
  { to: "/explorer", label: "Explorer", icon: "explorer" },
  { to: "/analytics", label: "Analytics", icon: "analytics" },
  { to: "/recommendations", label: "Recommendations", short: "Advice", icon: "recommendations" },
  { to: "/insights", label: "Insights", icon: "insights" },
];

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
  const location = useLocation();
  const outlet = useOutlet();
  const reduce = useReducedMotion();
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
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={location.pathname}
            initial={reduce ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduce ? undefined : { opacity: 0, y: -6 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
          >
            {outlet}
          </motion.div>
        </AnimatePresence>
      </main>

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
