import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getErrorMessage } from "../api/client";
import { getCalendar } from "../api/endpoints";
import type { CalendarDayRead } from "../api/types";
import { useSelectedDate } from "../context/SelectedDateContext";
import { endOfWeek, formatDateInput, parseDateInput, startOfWeek } from "../utils/date";

const WEEK_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function Calendar() {
  const navigate = useNavigate();
  const { selectedDate, setSelectedDate } = useSelectedDate();
  const [activeMonth, setActiveMonth] = useState(() => {
    const selected = parseDateInput(selectedDate);
    return new Date(selected.getFullYear(), selected.getMonth(), 1);
  });
  const [calendarDays, setCalendarDays] = useState<CalendarDayRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const monthLabel = useMemo(
    () =>
      new Intl.DateTimeFormat(undefined, {
        month: "long",
        year: "numeric",
      }).format(activeMonth),
    [activeMonth],
  );

  const dateFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat(undefined, {
        weekday: "short",
        month: "short",
        day: "numeric",
      }),
    [],
  );

  const grid = useMemo(() => {
    const monthStart = new Date(activeMonth.getFullYear(), activeMonth.getMonth(), 1);
    const monthEnd = new Date(activeMonth.getFullYear(), activeMonth.getMonth() + 1, 0);
    const gridStart = startOfWeek(monthStart, 1);
    const gridEnd = endOfWeek(monthEnd, 1);
    const dates: string[] = [];
    const cursor = new Date(gridStart);
    while (cursor <= gridEnd) {
      dates.push(formatDateInput(cursor));
      cursor.setDate(cursor.getDate() + 1);
    }
    return {
      dates,
      monthIndex: activeMonth.getMonth(),
      startDate: formatDateInput(gridStart),
      endDate: formatDateInput(gridEnd),
    };
  }, [activeMonth]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getCalendar(grid.startDate, grid.endDate);
        if (!cancelled) {
          setCalendarDays(data);
          setLoading(false);
        }
      } catch (errorValue) {
        if (!cancelled) {
          setError(getErrorMessage(errorValue));
          setLoading(false);
        }
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [grid.endDate, grid.startDate, reloadToken]);

  const dayMap = useMemo(() => {
    return new Map(calendarDays.map((day) => [day.date, day]));
  }, [calendarDays]);

  return (
    <section className="page calendar-page">
      <div className="card calendar-header">
        <div>
          <div className="calendar-header__label">Month view</div>
          <div className="calendar-header__value">{monthLabel}</div>
        </div>
        <div className="calendar-nav">
          <button
            className="icon-button"
            type="button"
            onClick={() =>
              setActiveMonth(
                (prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1),
              )
            }
            aria-label="Previous month"
          >
            &#8592;
          </button>
          <button
            className="icon-button"
            type="button"
            onClick={() =>
              setActiveMonth(
                (prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1),
              )
            }
            aria-label="Next month"
          >
            &#8594;
          </button>
        </div>
      </div>

      <div className="card">
        {loading ? (
          <div className="status status--loading">Loading calendar...</div>
        ) : error ? (
          <div className="status status--error" role="alert">
            <div>Could not load calendar. {error}</div>
            <button
              className="action-button"
              type="button"
              onClick={() => setReloadToken((prev) => prev + 1)}
            >
              Retry
            </button>
          </div>
        ) : (
          <div className="calendar-grid">
            {WEEK_LABELS.map((label) => (
              <div key={label} className="calendar-grid__label">
                {label}
              </div>
            ))}
            {grid.dates.map((date) => {
              const day = dayMap.get(date);
              const parsed = parseDateInput(date);
              const isOutsideMonth = parsed.getMonth() !== grid.monthIndex;
              const isSelected = date === selectedDate;
              const applicable = day?.applicable_goals ?? 0;
              const met = day?.met_goals ?? 0;
              const ratio = day?.completion_ratio ?? 0;
              const percent = Math.max(0, Math.min(100, Math.round(ratio * 100)));
              const conditions = (day?.conditions ?? []).filter(
                (condition) => condition.value,
              );
              const visibleConditions = conditions.slice(0, 3);
              const extraCount = conditions.length - visibleConditions.length;

              return (
                <button
                  key={date}
                  className={`calendar-day${isOutsideMonth ? " calendar-day--outside" : ""}${
                    isSelected ? " calendar-day--selected" : ""
                  }`}
                  type="button"
                  onClick={() => {
                    setSelectedDate(date);
                    navigate("/today");
                  }}
                  aria-label={`Open ${dateFormatter.format(parsed)}`}
                >
                  <div className="calendar-day__number">{parsed.getDate()}</div>
                  <div className="calendar-day__summary">
                    <span>
                      {met}/{applicable} met
                    </span>
                    <span className="calendar-day__percent">{percent}%</span>
                  </div>
                  <div className="calendar-day__bar">
                    <span style={{ width: `${percent}%` }} />
                  </div>
                  {visibleConditions.length > 0 && (
                    <div className="calendar-day__badges">
                      {visibleConditions.map((condition) => (
                        <span
                          key={condition.condition_id}
                          className="calendar-badge"
                        >
                          {condition.name}
                        </span>
                      ))}
                      {extraCount > 0 && (
                        <span className="calendar-badge calendar-badge--muted">
                          +{extraCount}
                        </span>
                      )}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
