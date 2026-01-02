import { useCallback, useEffect, useState } from "react";
import { getErrorMessage } from "../api/client";
import { listConditions } from "../api/endpoints";
import type { ConditionRead } from "../api/types";

type ConditionsState = {
  conditions: ConditionRead[];
  loading: boolean;
  error: string | null;
};

export function useConditions() {
  const [state, setState] = useState<ConditionsState>({
    conditions: [],
    loading: true,
    error: null,
  });

  const reload = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await listConditions();
      setState({ conditions: data, loading: false, error: null });
    } catch (error) {
      setState({ conditions: [], loading: false, error: getErrorMessage(error) });
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setState((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const data = await listConditions();
        if (!cancelled) {
          setState({ conditions: data, loading: false, error: null });
        }
      } catch (error) {
        if (!cancelled) {
          setState({
            conditions: [],
            loading: false,
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

  return {
    conditions: state.conditions,
    loading: state.loading,
    error: state.error,
    reload,
  };
}
