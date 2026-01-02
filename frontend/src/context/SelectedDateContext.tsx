import { createContext, useContext, useMemo, useState } from "react";
import type { Dispatch, ReactNode, SetStateAction } from "react";
import { formatDateInput } from "../utils/date";

type SelectedDateContextValue = {
  selectedDate: string;
  setSelectedDate: Dispatch<SetStateAction<string>>;
};

const SelectedDateContext = createContext<SelectedDateContextValue | undefined>(undefined);

export function SelectedDateProvider({ children }: { children: ReactNode }) {
  const [selectedDate, setSelectedDate] = useState(() =>
    formatDateInput(new Date()),
  );

  const value = useMemo(
    () => ({
      selectedDate,
      setSelectedDate,
    }),
    [selectedDate],
  );

  return (
    <SelectedDateContext.Provider value={value}>
      {children}
    </SelectedDateContext.Provider>
  );
}

export function useSelectedDate() {
  const context = useContext(SelectedDateContext);
  if (!context) {
    throw new Error("useSelectedDate must be used within SelectedDateProvider");
  }
  return context;
}
