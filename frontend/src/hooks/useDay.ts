import { useCallback, useEffect, useState } from "react";
import type { SetStateAction } from "react";
import { getErrorMessage } from "../api/client";
import { getDay } from "../api/endpoints";
import type { DayRead } from "../api/types";

type DayState = {
  day: DayRead | null;
  loading: boolean;
  error: string | null;
};

export function useDay(date: string) {
  const [state, setState] = useState<DayState>({
    day: null,
    loading: true,
    error: null,
  });

  const reload = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await getDay(date);
      setState({ day: data, loading: false, error: null });
    } catch (error) {
      setState({ day: null, loading: false, error: getErrorMessage(error) });
    }
  }, [date]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setState({ day: null, loading: true, error: null });
      try {
        const data = await getDay(date);
        if (!cancelled) {
          setState({ day: data, loading: false, error: null });
        }
      } catch (error) {
        if (!cancelled) {
          setState({ day: null, loading: false, error: getErrorMessage(error) });
        }
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [date]);

  return {
    day: state.day,
    setDay: (updater: SetStateAction<DayRead | null>) => {
      setState((prev) => ({
        ...prev,
        day: typeof updater === "function" ? updater(prev.day) : updater,
      }));
    },
    loading: state.loading,
    error: state.error,
    reload,
  };
}
