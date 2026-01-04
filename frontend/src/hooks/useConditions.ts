import { useCallback, useEffect, useState } from "react";
import { getErrorMessage } from "../api/client";
import { listConditions } from "../api/endpoints";
import type { ConditionRead } from "../api/types";

type ConditionsState = {
  conditions: ConditionRead[];
  loading: boolean;
  error: string | null;
};

export function useConditions(options?: { includeInactive?: boolean }) {
  const [state, setState] = useState<ConditionsState>({
    conditions: [],
    loading: true,
    error: null,
  });

  const reload = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await listConditions(options);
      setState({ conditions: data, loading: false, error: null });
    } catch (error) {
      setState({ conditions: [], loading: false, error: getErrorMessage(error) });
    }
  }, [options?.includeInactive]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setState((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const data = await listConditions(options);
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
  }, [options?.includeInactive]);

  return {
    conditions: state.conditions,
    setConditions: (
      updater: ((prev: ConditionRead[]) => ConditionRead[]) | ConditionRead[],
    ) => {
      setState((prev) => ({
        ...prev,
        conditions: typeof updater === "function" ? updater(prev.conditions) : updater,
      }));
    },
    loading: state.loading,
    error: state.error,
    reload,
  };
}
