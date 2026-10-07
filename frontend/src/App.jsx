/**
 * Workspace Monitor — root component: sign-in gate, workspace context and routes.
 * Heavier pages are split into their own chunks.
 */

import { lazy, Suspense, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/shell/AppShell";
import Login from "./pages/Login";
import Live from "./pages/Live";
import { WorkspaceProvider } from "./lib/workspace";
import { getAuthToken, getCurrentUser } from "./api/client";
import { Skeleton } from "./components/feedback";

const Analytics = lazy(() => import("./pages/Analytics"));
const Recommendations = lazy(() => import("./pages/Recommendations"));
const Explorer = lazy(() => import("./pages/Explorer"));
const Insights = lazy(() => import("./pages/Insights"));
const Session = lazy(() => import("./pages/Session"));

function PageFallback() {
  return (
    <div className="page">
      <Skeleton height={44} width="36%" />
      <Skeleton height={320} style={{ marginTop: 24 }} />
    </div>
  );
}

export default function App() {
  const [auth, setAuth] = useState(getAuthToken() ? "checking" : "signed-out");

  useEffect(() => {
    if (auth !== "checking") return;
    getCurrentUser()
      .then((user) => {
        try {
          localStorage.setItem("user_name", user.full_name);
        } catch {
          /* ignore */
        }
        setAuth("signed-in");
      })
      .catch(() => setAuth("signed-out"));
  }, [auth]);

  useEffect(() => {
    const onExpired = () => setAuth("signed-out");
    window.addEventListener("auth:expired", onExpired);
    return () => window.removeEventListener("auth:expired", onExpired);
  }, []);

  if (auth === "checking") return <PageFallback />;

  if (auth === "signed-out") {
    return (
      <Login
        onLoginSuccess={(user) => {
          try {
            localStorage.setItem("user_name", user.full_name);
          } catch {
            /* ignore */
          }
          setAuth("signed-in");
        }}
      />
    );
  }

  return (
    <BrowserRouter>
      <WorkspaceProvider>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route path="/" element={<AppShell />}>
              <Route index element={<Live />} />
              <Route path="analytics" element={<Analytics />} />
              <Route path="recommendations" element={<Recommendations />} />
              <Route path="explorer" element={<Explorer />} />
              <Route path="insights" element={<Insights />} />
              <Route path="sessions/:sessionId" element={<Session />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </Suspense>
      </WorkspaceProvider>
    </BrowserRouter>
  );
}
