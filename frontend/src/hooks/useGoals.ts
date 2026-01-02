import { useCallback, useEffect, useState } from "react";
import { getErrorMessage } from "../api/client";
import { listGoals } from "../api/endpoints";
import type { GoalRead } from "../api/types";

type GoalsState = {
  goals: GoalRead[];
  loading: boolean;
  error: string | null;
};

export function useGoals() {
  const [state, setState] = useState<GoalsState>({
    goals: [],
    loading: true,
    error: null,
  });

  const reload = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await listGoals();
      setState({ goals: data, loading: false, error: null });
    } catch (error) {
      setState({ goals: [], loading: false, error: getErrorMessage(error) });
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setState((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const data = await listGoals();
        if (!cancelled) {
          setState({ goals: data, loading: false, error: null });
        }
      } catch (error) {
        if (!cancelled) {
          setState({ goals: [], loading: false, error: getErrorMessage(error) });
        }
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, []);

  return {
    goals: state.goals,
    setGoals: (updater: ((prev: GoalRead[]) => GoalRead[]) | GoalRead[]) => {
      setState((prev) => ({
        ...prev,
        goals: typeof updater === "function" ? updater(prev.goals) : updater,
      }));
    },
    loading: state.loading,
    error: state.error,
    reload,
  };
}
