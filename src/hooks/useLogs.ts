import { useCallback, useEffect, useRef, useState } from "react";
import { backend } from "../lib/backend";
import type { LogEntry } from "../lib/types";

export const VISIBLE_LOGS = 50;
const MEMORY_LOGS = 10_000;

/**
 * Collects the analysed messages while the logs are enabled: the latest 50 are shown, and the whole
 * session (up to 10 000 lines) is kept in memory for the "Enregistrer les logs" file. Nothing else is kept.
 */
export function useLogs(enabled: boolean): { visible: LogEntry[]; all: () => LogEntry[]; count: number; clear: () => void } {
  const memory = useRef<LogEntry[]>([]);
  const [visible, setVisible] = useState<LogEntry[]>([]);
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!enabled) return undefined;
    return backend.onLog((entry) => {
      memory.current.push(entry);
      if (memory.current.length > MEMORY_LOGS) memory.current.shift();
      setVisible(memory.current.slice(-VISIBLE_LOGS).reverse());
      setCount(memory.current.length);
    });
  }, [enabled]);

  const all = useCallback(() => [...memory.current], []);
  const clear = useCallback(() => {
    memory.current = [];
    setVisible([]);
    setCount(0);
  }, []);
  return { visible, all, count, clear };
}
