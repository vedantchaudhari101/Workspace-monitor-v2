/**
 * Workspace Monitor — root component: sign-in gate, workspace context and routes.
 * Heavier pages are split into their own chunks.
 */

import { lazy, Suspense, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/shell/AppShell";
import Intro from "./components/shell/Intro";
import Login from "./pages/Login";
import Live from "./pages/Live";
import { WorkspaceProvider } from "./lib/workspace";
import { getAuthToken, getCurrentUser } from "./api/client";
import { Skeleton } from "./components/feedback";

const loaders = {
  analytics: () => import("./pages/Analytics"),
  recommendations: () => import("./pages/Recommendations"),
  explorer: () => import("./pages/Explorer"),
  insights: () => import("./pages/Insights"),
  session: () => import("./pages/Session"),
};
const Analytics = lazy(loaders.analytics);
const Recommendations = lazy(loaders.recommendations);
const Explorer = lazy(loaders.explorer);
const Insights = lazy(loaders.insights);
const Session = lazy(loaders.session);

// Fetch the other pages in the background after sign-in so switching is instant.
function preloadPages() {
  const go = () => Object.values(loaders).forEach((load) => load().catch(() => {}));
  if ("requestIdleCallback" in window) window.requestIdleCallback(go, { timeout: 3000 });
  else setTimeout(go, 1500);
}

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
    if (auth === "signed-in") preloadPages();
  }, [auth]);

  useEffect(() => {
    const onExpired = () => setAuth("signed-out");
    window.addEventListener("auth:expired", onExpired);
    return () => window.removeEventListener("auth:expired", onExpired);
  }, []);

  let content;
  if (auth === "checking") {
    content = <PageFallback />;
  } else if (auth === "signed-out") {
    content = (
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
  } else {
    content = (
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

  // The intro sits outside the branches so it keeps playing while sign-in is checked.
  return (
    <>
      {content}
      <Intro />
    </>
  );
}
