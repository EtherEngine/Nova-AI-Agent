import { useEffect, useState } from "react";

import { api } from "@/services/api";
import type { ConnectionStatus } from "@/types";

const POLL_INTERVAL_MS = 30_000;

export interface UseHealth {
  status: ConnectionStatus;
  model: string | null;
}

/** Polls the backend `/health` endpoint to surface connection state + model. */
export function useHealth(): UseHealth {
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [model, setModel] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();

    const check = async () => {
      try {
        const health = await api.health(controller.signal);
        if (!active) return;
        setModel(health.model);
        setStatus("online");
      } catch {
        if (!active) return;
        setStatus("offline");
      }
    };

    void check();
    const interval = setInterval(() => void check(), POLL_INTERVAL_MS);

    return () => {
      active = false;
      controller.abort();
      clearInterval(interval);
    };
  }, []);

  return { status, model };
}
