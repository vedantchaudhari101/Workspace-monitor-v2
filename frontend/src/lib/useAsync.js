import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Run an async loader when its dependencies change.
 * Returns { data, error, loading, reload }. Stale responses are ignored.
 */
export function useAsync(loader, deps, { enabled = true, keepPrevious = true } = {}) {
  const [state, setState] = useState({ data: undefined, error: null, loading: enabled });
  const seq = useRef(0);

  const run = useCallback(async () => {
    if (!enabled) return;
    const id = ++seq.current;
    setState((s) => ({ data: keepPrevious ? s.data : undefined, error: null, loading: true }));
    try {
      const data = await loader();
      if (id === seq.current) setState({ data, error: null, loading: false });
    } catch (error) {
      if (id === seq.current) setState((s) => ({ data: keepPrevious ? s.data : undefined, error, loading: false }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, ...deps]);

  useEffect(() => {
    run();
  }, [run]);

  return { ...state, reload: run };
}

/** Re-run a callback on an interval while the tab is visible. */
export function useInterval(callback, ms, enabled = true) {
  const saved = useRef(callback);
  useEffect(() => {
    saved.current = callback;
  }, [callback]);
  useEffect(() => {
    if (!enabled || !ms) return undefined;
    const id = setInterval(() => {
      if (document.visibilityState === "visible") saved.current();
    }, ms);
    return () => clearInterval(id);
  }, [ms, enabled]);
}
