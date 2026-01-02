import { useEffect, useState } from "react";
import { getErrorMessage } from "../api/client";
import { getHealth } from "../api/endpoints";
import type { HealthResponse } from "../api/types";

type HealthState = {
  loading: boolean;
  data: HealthResponse | null;
  error: string | null;
};

export default function HealthStatus() {
  const [state, setState] = useState<HealthState>({
    loading: true,
    data: null,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const data = await getHealth();
        if (!cancelled) {
          setState({ loading: false, data, error: null });
        }
      } catch (error) {
        if (!cancelled) {
          setState({
            loading: false,
            data: null,
            error: getErrorMessage(error),
          });
        }
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, []);

  if (state.loading) {
    return <div className="status status--loading">Checking API...</div>;
  }

  if (state.error) {
    return (
      <div className="status status--error">
        <span>API unavailable.</span>
        <span className="status-detail">{state.error}</span>
      </div>
    );
  }

  return (
    <div className="status status--ok">
      API status: <strong>{state.data?.status ?? "ok"}</strong>
    </div>
  );
}
