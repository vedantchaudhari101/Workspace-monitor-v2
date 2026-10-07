/**
 * Typed-ish wrappers around the REST API. Every function returns the JSON body.
 */

import apiClient from "./client";

export const tzOffsetMinutes = () => -new Date().getTimezoneOffset();

export const api = {
  config: () => apiClient.get("/config"),
  context: (buildingId) => apiClient.get("/workspace/context", { params: buildingId ? { building_id: buildingId } : {} }),
  map: (buildingId, params) => apiClient.get(`/workspace/map/${buildingId}`, { params }),

  analytics: (buildingId, params) =>
    apiClient.get(`/analytics/comprehensive/${buildingId}`, { params: { tz_offset_minutes: tzOffsetMinutes(), ...params } }),
  insights: (buildingId, params) =>
    apiClient.get(`/analytics/insights/${buildingId}`, { params: { tz_offset_minutes: tzOffsetMinutes(), ...params } }),
  activity: (buildingId, params) => apiClient.get(`/analytics/activity/${buildingId}`, { params }),
  seatHistory: (seatId, params) => apiClient.get(`/analytics/seats/${seatId}/history`, { params }),
  forecast: (buildingId, daysAhead = 3) =>
    apiClient.get("/analytics/forecast", { params: { building_id: buildingId, days_ahead: daysAhead } }),

  cameraState: (cameraId) => apiClient.get(`/occupancy/camera/${cameraId}/state`),
  runSample: (cameraId) => apiClient.post(`/occupancy/camera/${cameraId}/sample`),
  stopCamera: (cameraId) => apiClient.post(`/occupancy/camera/${cameraId}/stop`),
  uploadVideo: (cameraId, file, onProgress) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post(`/occupancy/camera/${cameraId}/upload-video`, form, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 0,
      onUploadProgress: (e) => onProgress?.(e.total ? e.loaded / e.total : 0, e.loaded, e.total),
    });
  },
  sessions: (params) => apiClient.get("/occupancy/sessions", { params }),
  session: (sessionId) => apiClient.get(`/occupancy/sessions/${sessionId}`),

  recommendations: (params) => apiClient.get("/recommendations", { params }),
  scanRecommendations: () => apiClient.post("/recommendations/scan"),
  approveRecommendation: (id) => apiClient.post(`/recommendations/${id}/approve`),
  rejectRecommendation: (id) => apiClient.post(`/recommendations/${id}/reject`),

  allocateSeat: (seatId, startupId) => apiClient.post("/seats/allocations", { seat_id: seatId, startup_id: startupId }),
  releaseAllocation: (allocationId) => apiClient.put(`/seats/allocations/${allocationId}`, { is_active: false }),
};
