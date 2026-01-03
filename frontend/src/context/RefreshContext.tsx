import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

type RefreshContextValue = {
  refreshToken: number;
  bumpRefreshToken: () => void;
};

const RefreshContext = createContext<RefreshContextValue | undefined>(undefined);

export function RefreshProvider({ children }: { children: ReactNode }) {
  const [refreshToken, setRefreshToken] = useState(0);

  const bumpRefreshToken = useCallback(() => {
    setRefreshToken((prev) => prev + 1);
  }, []);

  const value = useMemo(
    () => ({
      refreshToken,
      bumpRefreshToken,
    }),
    [refreshToken, bumpRefreshToken],
  );

  return <RefreshContext.Provider value={value}>{children}</RefreshContext.Provider>;
}

export function useRefresh() {
  const context = useContext(RefreshContext);
  if (!context) {
    throw new Error("useRefresh must be used within RefreshProvider");
  }
  return context;
}
