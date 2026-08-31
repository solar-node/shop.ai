import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";

const POLL_MS = 250;

export function useLedger(sessionId, active = false, onStateUpdate) {
  const [events, setEvents] = useState([]);
  const lastId = useRef(null);
  const count = useRef(0);

  const fetchLedger = useCallback(async () => {
    if (!sessionId) return;
    try {
      const data = await api.getLedger(sessionId);
      const incoming = data.events || [];
      const id = incoming.at(-1)?.id ?? null;

      if (incoming.length !== count.current || id !== lastId.current) {
        count.current = incoming.length;
        lastId.current = id;
        setEvents(incoming);
      }

      if (onStateUpdate) {
        const state = await api.getState(sessionId);
        if (state?.state) onStateUpdate(state.state);
      }
    } catch {
      // A temporary polling failure should not break the UI.
    }
  }, [sessionId, onStateUpdate]);

  useEffect(() => {
    if (!active || !sessionId) return;
    fetchLedger();
    const timer = setInterval(fetchLedger, POLL_MS);
    return () => clearInterval(timer);
  }, [active, sessionId, fetchLedger]);

  const clear = useCallback(() => {
    setEvents([]);
    count.current = 0;
    lastId.current = null;
  }, []);

  return { events, clear };
}
