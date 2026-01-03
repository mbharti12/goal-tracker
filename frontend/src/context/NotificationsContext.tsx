import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { getErrorMessage } from "../api/client";
import { listNotifications } from "../api/endpoints";
import type { NotificationRead } from "../api/types";

type NotificationsState = {
  notifications: NotificationRead[];
  loading: boolean;
  error: string | null;
};

type NotificationsContextValue = {
  notifications: NotificationRead[];
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  setNotifications: (
    updater: ((prev: NotificationRead[]) => NotificationRead[]) | NotificationRead[],
  ) => void;
};

const NotificationsContext = createContext<NotificationsContextValue | undefined>(undefined);
const POLL_INTERVAL_MS = 30000;

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<NotificationsState>({
    notifications: [],
    loading: true,
    error: null,
  });

  const loadNotifications = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setState((prev) => ({ ...prev, loading: true, error: null }));
    }
    try {
      const data = await listNotifications();
      setState({ notifications: data, loading: false, error: null });
    } catch (error) {
      if (!options?.silent) {
        setState({
          notifications: [],
          loading: false,
          error: getErrorMessage(error),
        });
      }
    }
  }, []);

  const reload = useCallback(async () => {
    await loadNotifications();
  }, [loadNotifications]);

  useEffect(() => {
    void loadNotifications();
  }, [loadNotifications]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void loadNotifications({ silent: true });
    }, POLL_INTERVAL_MS);

    return () => window.clearInterval(interval);
  }, [loadNotifications]);

  const setNotifications = useCallback(
    (updater: ((prev: NotificationRead[]) => NotificationRead[]) | NotificationRead[]) => {
      setState((prev) => ({
        ...prev,
        notifications: typeof updater === "function" ? updater(prev.notifications) : updater,
      }));
    },
    [],
  );

  const value = useMemo(
    () => ({
      notifications: state.notifications,
      loading: state.loading,
      error: state.error,
      reload,
      setNotifications,
    }),
    [reload, setNotifications, state.error, state.loading, state.notifications],
  );

  return (
    <NotificationsContext.Provider value={value}>
      {children}
    </NotificationsContext.Provider>
  );
}

export function useNotifications() {
  const context = useContext(NotificationsContext);
  if (!context) {
    throw new Error("useNotifications must be used within NotificationsProvider");
  }
  return context;
}
