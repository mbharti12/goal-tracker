import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import BottomTabs, { TAB_ITEMS } from "./components/BottomTabs";
import Calendar from "./pages/Calendar";
import Goals from "./pages/Goals";
import Review from "./pages/Review";
import Today from "./pages/Today";
import { getErrorMessage } from "./api/client";
import { getHealth } from "./api/endpoints";

export default function App() {
  const location = useLocation();
  const [apiError, setApiError] = useState<string | null>(null);

  const activeTab = useMemo(() => {
    return (
      TAB_ITEMS.find((tab) => location.pathname.startsWith(tab.path)) ??
      TAB_ITEMS[0]
    );
  }, [location.pathname]);

  const dateLabel = useMemo(() => {
    return new Intl.DateTimeFormat(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
    }).format(new Date());
  }, []);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        await getHealth();
        if (!cancelled) {
          setApiError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setApiError(getErrorMessage(error));
        }
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="app-shell">
      <header className="top-bar">
        <div className="top-bar__date">
          <span className="top-bar__label">Local date</span>
          <span className="top-bar__value">{dateLabel}</span>
        </div>
        <div className="top-bar__title">{activeTab.label}</div>
      </header>

      {apiError && (
        <div className="error-banner" role="alert">
          <div className="error-banner__title">Backend unreachable</div>
          <div className="error-banner__body">
            Running in offline mode. {apiError}
          </div>
        </div>
      )}

      <main className="content">
        <Routes>
          <Route path="/" element={<Navigate to="/today" replace />} />
          <Route path="/today" element={<Today />} />
          <Route path="/goals" element={<Goals />} />
          <Route path="/calendar" element={<Calendar />} />
          <Route path="/review" element={<Review />} />
        </Routes>
      </main>

      <BottomTabs />
    </div>
  );
}
