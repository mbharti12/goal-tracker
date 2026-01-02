import { useCallback, useEffect, useState } from "react";
import { getErrorMessage } from "../api/client";
import { listTags } from "../api/endpoints";
import type { TagRead } from "../api/types";

type TagsState = {
  tags: TagRead[];
  loading: boolean;
  error: string | null;
};

export function useTags(options?: { includeInactive?: boolean }) {
  const [state, setState] = useState<TagsState>({
    tags: [],
    loading: true,
    error: null,
  });

  const reload = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await listTags(options);
      setState({ tags: data, loading: false, error: null });
    } catch (error) {
      setState({ tags: [], loading: false, error: getErrorMessage(error) });
    }
  }, [options?.includeInactive]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setState((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const data = await listTags(options);
        if (!cancelled) {
          setState({ tags: data, loading: false, error: null });
        }
      } catch (error) {
        if (!cancelled) {
          setState({ tags: [], loading: false, error: getErrorMessage(error) });
        }
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [options?.includeInactive]);

  return {
    tags: state.tags,
    setTags: (updater: ((prev: TagRead[]) => TagRead[]) | TagRead[]) => {
      setState((prev) => ({
        ...prev,
        tags: typeof updater === "function" ? updater(prev.tags) : updater,
      }));
    },
    loading: state.loading,
    error: state.error,
    reload,
  };
}
