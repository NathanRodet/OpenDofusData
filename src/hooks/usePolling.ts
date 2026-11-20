import { useCallback, useEffect, useRef, useState } from "react";

/** Calls `load` now and every `periodMs`; returns the last value and a function to refresh at once. */
export function usePolling<T>(load: () => Promise<T>, periodMs: number): [T | null, () => void] {
  const [value, setValue] = useState<T | null>(null);
  const loader = useRef(load);
  loader.current = load;

  const refresh = useCallback(() => {
    loader.current().then(setValue).catch(() => setValue(null));
  }, []);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, periodMs);
    return () => window.clearInterval(timer);
  }, [refresh, periodMs]);

  return [value, refresh];
}
