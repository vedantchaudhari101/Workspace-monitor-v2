/**
 * Workspace context: which building and camera the user is looking at, the
 * startups available for seat assignment, and whether demo data is included.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../api/endpoints";

const WorkspaceContext = createContext(null);
const DEMO_KEY = "wm.includeDemo";
const CAMERA_KEY = "wm.camera";

function readPref(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writePref(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable — preference lasts for this visit only */
  }
}

export function WorkspaceProvider({ children }) {
  const [ctx, setCtx] = useState(null);
  const [error, setError] = useState(null);
  const [cameraId, setCameraIdState] = useState(readPref(CAMERA_KEY));
  const [includeDemo, setIncludeDemoState] = useState(() => {
    const v = readPref(DEMO_KEY);
    return v === null ? null : v === "true";
  });

  const [config, setConfig] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    api.config().then(setConfig).catch(() => {});
    try {
      const data = await api.context();
      setCtx(data);
      setCameraIdState((cur) => (cur && data.cameras.some((c) => c.id === cur) ? cur : data.cameras[0]?.id || null));
    } catch (e) {
      setError(e);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const setCameraId = useCallback((id) => {
    setCameraIdState(id);
    writePref(CAMERA_KEY, id);
  }, []);

  const setIncludeDemo = useCallback((v) => {
    setIncludeDemoState(v);
    writePref(DEMO_KEY, String(v));
  }, []);

  const value = useMemo(() => {
    const demo = includeDemo === null ? !!ctx?.demo_mode : includeDemo;
    return {
      ready: !!ctx,
      error,
      reload: load,
      building: ctx?.building || null,
      buildingId: ctx?.building?.id || null,
      cameras: ctx?.cameras || [],
      camera: ctx?.cameras?.find((c) => c.id === cameraId) || null,
      cameraId,
      setCameraId,
      startups: ctx?.startups || [],
      demoMode: !!ctx?.demo_mode,
      demoDataPresent: !!ctx?.demo_data_present,
      includeDemo: demo,
      setIncludeDemo,
      pipeline: ctx?.pipeline,
      maxUploadMb: ctx?.max_upload_mb || 500,
      sample: config?.sample_video?.available ? config.sample_video : null,
    };
  }, [ctx, config, error, load, cameraId, setCameraId, includeDemo, setIncludeDemo]);

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const v = useContext(WorkspaceContext);
  if (!v) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return v;
}
