/**
 * Workspace Monitor — Root Application Component
 *
 * Sets up React Router with the application layout and page routes.
 * All routes are rendered inside the Layout component which provides
 * the persistent sidebar and app bar.
 *
 * Route Structure:
 * /              → Dashboard (Phase 1)
 * /live-map      → Live Seat Map (Phase 4)
 * /analytics     → Analytics (Phase 5)
 * /trends        → Occupancy Trends (Phase 5)
 * /revenue       → Revenue Dashboard (Phase 5)
 * /recommendations → Recommendations (Phase 6)
 * /settings      → Admin Settings (Phase 7)
 *
 * Dependencies: react-router-dom, Layout component, page components
 */

import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Analytics from "./pages/Analytics";
import Recommendations from "./pages/Recommendations";
import Login from "./pages/Login";
import { getAuthToken, getCurrentUser } from "./api/client";

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!getAuthToken());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      const token = getAuthToken();
      if (token) {
        try {
          const user = await getCurrentUser();
          localStorage.setItem("user_name", user.full_name);
          localStorage.setItem("user_email", user.email);
          setIsAuthenticated(true);
        } catch (err) {
          console.error("Token verification failed:", err);
          setIsAuthenticated(false);
        }
      } else {
        setIsAuthenticated(false);
      }
      setLoading(false);
    };

    initAuth();
  }, []);

  const handleLoginSuccess = (user) => {
    localStorage.setItem("user_name", user.full_name);
    localStorage.setItem("user_email", user.email);
    setIsAuthenticated(true);
  };

  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          minHeight: "100vh",
          fontFamily: "Nunito, sans-serif",
          backgroundColor: "#F7F7F7",
        }}
      >
        <h3 style={{ color: "#4B4B4B", fontWeight: 800 }}>Loading Workspace Monitor...</h3>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          {/* Phase 1 — Active */}
          <Route index element={<Dashboard />} />

          {/* Phase 5 — Analytics */}
          <Route
            path="analytics"
            element={<Analytics />}
          />

          {/* Phase 6 — Recommendations */}
          <Route
            path="recommendations"
            element={<Recommendations />}
          />

          {/* Catch-all → redirect to dashboard */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
