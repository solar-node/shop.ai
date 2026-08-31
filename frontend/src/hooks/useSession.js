import { useCallback, useState } from "react";
import { api } from "../api/client";

export function useSession() {
  const [sessionId, setSessionId] = useState(null);
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [backendOnline, setBackendOnline] = useState(null);

  const ensureSession = useCallback(async () => {
    if (sessionId) return sessionId;
    const data = await api.createSession();
    setSessionId(data.session_id);
    return data.session_id;
  }, [sessionId]);

  const checkHealth = useCallback(async () => {
    try {
      await api.health();
      setBackendOnline(true);
    } catch {
      setBackendOnline(false);
    }
  }, []);

  const run = useCallback(async (goal, simulateOos = false, simulatePaymentTimeout = false) => {
    setLoading(true);
    setError(null);
    try {
      const id = await ensureSession();
      const result = await api.run(id, goal, simulateOos, simulatePaymentTimeout);
      setState(result);
      return result;
    } catch (e) {
      setError(e.message);
      throw e;
    } finally {
      setLoading(false);
    }
  }, [ensureSession]);

  const confirm = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const result = await api.confirm(sessionId);
      setState(result);
      return result;
    } catch (e) {
      setError(e.message);
      throw e;
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  const poll = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const result = await api.poll(sessionId);
      setState(result);
      return result;
    } catch (e) {
      setError(e.message);
      throw e;
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  const resetSession = useCallback(() => {
    setSessionId(null);
    setState(null);
    setError(null);
  }, []);

  return {
    sessionId, state, setState, loading, error, backendOnline,
    run, confirm, poll, checkHealth, resetSession,
  };
}
