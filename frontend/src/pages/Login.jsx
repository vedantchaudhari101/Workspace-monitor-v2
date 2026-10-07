/**
 * Sign in. In demo mode the page offers the demo account explicitly so a
 * visitor to a public showcase can get in; nothing signs in silently.
 */

import { useEffect, useState } from "react";
import { login, setAuthToken, getCurrentUser } from "../api/client";
import { api } from "../api/endpoints";
import AmbientField from "../components/shell/AmbientField";
import { Mark } from "../components/shell/AppShell";
import { Magnetic } from "../components/motion";
import "../components/shell/shell.css";
import "./pages.css";

export default function Login({ onLoginSuccess }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [demo, setDemo] = useState(null);

  useEffect(() => {
    api.config().then((c) => setDemo(c.demo_login || null)).catch(() => {});
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setError("Enter your email and password.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await login(email, password);
      setAuthToken(res.access_token, remember);
      const user = await getCurrentUser();
      onLoginSuccess(user);
    } catch (err) {
      setError(err.status === 401 ? "That email and password don't match an account." : err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="shell">
      <AmbientField />
      <div className="login">
        <section className="login-story">
          <div className="row">
            <Mark />
            <span className="rail-name">Workspace Monitor</span>
          </div>
          <div>
            <h1 className="login-headline">Every seat, measured from the camera you already have.</h1>
            <p className="muted" style={{ marginTop: 20, maxWidth: "52ch" }}>
              Upload footage of a workspace. The system finds the chairs, tracks who is sitting where, and turns it into utilization,
              peak hours and allocation advice for each team.
            </p>
          </div>
          <div className="login-points">
            <div>
              <strong>Finds the seats</strong>
              Calibrates the room from the first frames, no manual coordinates.
            </div>
            <div>
              <strong>Tracks occupancy</strong>
              Pose detection decides which person owns which chair.
            </div>
            <div>
              <strong>Measures use</strong>
              Time occupied, sessions and peaks per seat and per team.
            </div>
          </div>
        </section>

        <section className="login-panel" aria-labelledby="signin-title">
          <div>
            <h2 id="signin-title" className="section-title">
              Sign in
            </h2>
            <p className="small muted">Use your workspace account.</p>
          </div>
          <form className="login-form" onSubmit={submit} noValidate>
            <div className="field">
              <label htmlFor="email">Email</label>
              <input id="email" className="input" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                className="input"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <label className="row small muted" style={{ gap: 8 }}>
              <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} /> Keep me signed in on this device
            </label>
            {error && (
              <div className="notice notice-error" role="alert">
                {error}
              </div>
            )}
            <Magnetic>
              <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: "100%" }}>
                {loading ? "Signing in" : "Sign in"}
              </button>
            </Magnetic>
          </form>
          {demo && (
            <div className="notice small">
              <div>
                This is a public demo.{" "}
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => {
                    setEmail(demo.email);
                    setPassword(demo.password);
                  }}
                >
                  Fill in the demo account
                </button>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
