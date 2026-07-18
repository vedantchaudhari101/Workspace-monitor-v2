/**
 * Workspace Monitor — API Client
 *
 * Centralized HTTP client for all backend API communication.
 * Built on Axios with interceptors for auth token injection,
 * error normalization, and automatic token refresh support.
 *
 * Design Decisions:
 * - Single Axios instance ensures consistent configuration
 * - Request interceptor injects JWT from localStorage
 * - Response interceptor normalizes errors into a consistent shape
 * - Base URL sourced from Vite environment variable
 *
 * Dependencies: axios
 */

import axios from "axios";

// ─── Configuration ───────────────────────────────────────────────────────────

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const API_TIMEOUT = 30000; // 30 seconds

// ─── Token Management ────────────────────────────────────────────────────────

const TOKEN_KEY = "workspace_monitor_token";

/**
 * Store the authentication token in localStorage or sessionStorage.
 * @param {string} token - JWT access token
 * @param {boolean} rememberMe - Whether to persist session across page reloads
 */
export const setAuthToken = (token, rememberMe = false) => {
  if (rememberMe) {
    localStorage.setItem(TOKEN_KEY, token);
    sessionStorage.removeItem(TOKEN_KEY);
  } else {
    sessionStorage.setItem(TOKEN_KEY, token);
    localStorage.removeItem(TOKEN_KEY);
  }
};

/**
 * Retrieve the stored authentication token.
 * @returns {string|null} The stored JWT or null
 */
export const getAuthToken = () => {
  return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
};

/**
 * Remove the authentication token (logout).
 */
export const clearAuthToken = () => {
  localStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
};

// ─── Axios Instance ──────────────────────────────────────────────────────────

const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: API_TIMEOUT,
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});

// ─── Request Interceptor ─────────────────────────────────────────────────────

apiClient.interceptors.request.use(
  (config) => {
    const token = getAuthToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// ─── Response Interceptor ────────────────────────────────────────────────────

apiClient.interceptors.response.use(
  (response) => {
    // Return data directly for convenience
    return response.data;
  },
  (error) => {
    // Normalize error shape for consistent handling across components
    const normalizedError = {
      message: "An unexpected error occurred",
      status: null,
      detail: null,
    };

    if (error.response) {
      // Server responded with an error status
      normalizedError.status = error.response.status;
      normalizedError.message =
        error.response.data?.detail ||
        error.response.data?.message ||
        error.response.statusText;
      normalizedError.detail = error.response.data;

      // Handle authentication errors
      if (error.response.status === 401) {
        clearAuthToken();
        // Optionally redirect to login
        // window.location.href = '/login';
      }
    } else if (error.request) {
      // Request was made but no response received
      if (error.code === "ECONNABORTED" || error.message?.includes("timeout")) {
        normalizedError.message = "Upload timed out. Please check your network upload speed or verify the server configuration.";
      } else {
        normalizedError.message = "Unable to reach the backend server (FastAPI may be offline or restarting). Please check if it is running.";
      }
    } else {
      // Error in request configuration
      normalizedError.message = error.message;
    }

    return Promise.reject(normalizedError);
  }
);

// ─── API Methods ─────────────────────────────────────────────────────────────

/**
 * Health check — verify backend connectivity.
 * Hits the root /health endpoint (not under /api/v1).
 */
export const checkHealth = async () => {
  const response = await axios.get(`${API_BASE_URL}/health`);
  return response.data;
};

/**
 * Get API v1 status.
 */
export const getApiStatus = async () => {
  return apiClient.get("/status");
};

/**
 * Login user and retrieve token.
 */
export const login = async (email, password) => {
  return apiClient.post("/auth/login/json", { email, password });
};

/**
 * Get the current logged-in user profile.
 */
export const getCurrentUser = async () => {
  return apiClient.get("/auth/me");
};

export default apiClient;
