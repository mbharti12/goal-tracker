import { Fragment, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getErrorMessage } from "../api/client";
import { getCalendarSummary } from "../api/endpoints";
import type {
  CalendarDayRead,
  CalendarMonthRead,
  CalendarSummaryRead,
  CalendarWeekRead,
} from "../api/types";
import { useRefresh } from "../context/RefreshContext";
import { useSelectedDate } from "../context/SelectedDateContext";
import { endOfWeek, formatDateInput, parseDateInput, startOfWeek } from "../utils/date";

const WEEK_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const toPercent = (ratio?: number) => {
  const value = ratio ?? 0;
  return Math.max(0, Math.min(100, Math.round(value * 100)));
};

export default function Calendar() {
  const navigate = useNavigate();
  const { selectedDate, setSelectedDate } = useSelectedDate();
  const { refreshToken } = useRefresh();
  const [activeMonth, setActiveMonth] = useState(() => {
    const selected = parseDateInput(selectedDate);
    return new Date(selected.getFullYear(), selected.getMonth(), 1);
  });
  const [calendarSummary, setCalendarSummary] = useState<CalendarSummaryRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  const weekLabelFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
      }),
    [],
  );

  const monthStart = useMemo(
    () => new Date(activeMonth.getFullYear(), activeMonth.getMonth(), 1),
    [activeMonth],
  );

  const monthEnd = useMemo(
    () => new Date(activeMonth.getFullYear(), activeMonth.getMonth() + 1, 0),
    [activeMonth],
  );

  const monthRange = useMemo(
    () => ({
      start: formatDateInput(monthStart),
      end: formatDateInput(monthEnd),
    }),
    [monthStart, monthEnd],
  );

  const grid = useMemo(() => {
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
      monthIndex: monthStart.getMonth(),
      startDate: formatDateInput(gridStart),
      endDate: formatDateInput(gridEnd),
    };
  }, [monthEnd, monthStart]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getCalendarSummary(grid.startDate, grid.endDate);
        if (!cancelled) {
          setCalendarSummary(data);
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
  }, [grid.endDate, grid.startDate, refreshToken]);

  const dayMap = useMemo(() => {
    return new Map<string, CalendarDayRead>(
      (calendarSummary?.days ?? []).map((day) => [day.date, day]),
    );
  }, [calendarSummary]);

  const weekMap = useMemo(() => {
    return new Map<string, CalendarWeekRead>(
      (calendarSummary?.weeks ?? []).map((week) => [week.start, week]),
    );
  }, [calendarSummary]);

  const monthSummary = useMemo<CalendarMonthRead | null>(() => {
    const months = calendarSummary?.months ?? [];
    if (months.length === 0) {
      return null;
    }
    const directMatch = months.find(
      (month) => month.start === monthRange.start || month.end === monthRange.end,
    );
    if (directMatch) {
      return directMatch;
    }
    const targetStart = parseDateInput(monthRange.start);
    const targetEnd = parseDateInput(monthRange.end);
    return (
      months.find((month) => {
        const start = parseDateInput(month.start);
        const end = parseDateInput(month.end);
        return start <= targetEnd && end >= targetStart;
      }) ?? null
    );
  }, [calendarSummary, monthRange.end, monthRange.start]);

  const weeks = useMemo(() => {
    const rows: string[][] = [];
    for (let index = 0; index < grid.dates.length; index += 7) {
      rows.push(grid.dates.slice(index, index + 7));
    }
    return rows;
  }, [grid.dates]);

  const formatWeekRange = (start: string, end: string) => {
    const startDate = parseDateInput(start);
    const endDate = parseDateInput(end);
    return `${weekLabelFormatter.format(startDate)} - ${weekLabelFormatter.format(endDate)}`;
  };

  const monthPercent = toPercent(monthSummary?.completion_ratio);
  const monthApplicable = monthSummary?.applicable_goals ?? 0;
  const monthMet = monthSummary?.met_goals ?? 0;

  return (
    <section className="page calendar-page">
      <div className="card calendar-header">
        <div className="calendar-header__group">
          <div className="calendar-header__label">Month view</div>
          <div className="calendar-header__value">{monthLabel}</div>
        </div>
        <div className="calendar-summary-card">
          <div className="calendar-summary-card__label">Monthly goals</div>
          {monthSummary ? (
            <>
              <div className="calendar-summary-card__value">{monthPercent}%</div>
              <div className="calendar-summary-card__meta">
                {monthMet}/{monthApplicable} met
              </div>
              <div className="calendar-summary-card__bar">
                <span style={{ width: `${monthPercent}%` }} />
              </div>
            </>
          ) : (
            <div className="calendar-summary-card__empty">No summary yet</div>
          )}
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
          <>
            <div className="calendar-grid">
              {WEEK_LABELS.map((label) => (
                <div key={label} className="calendar-grid__label">
                  {label}
                </div>
              ))}
              <div className="calendar-grid__label calendar-grid__label--week">Week</div>
              {weeks.map((weekDates) => {
                const weekStart = weekDates[0];
                const weekEnd = weekDates[weekDates.length - 1] ?? weekStart;
                const weekSummary = weekMap.get(weekStart);
                const applicable = weekSummary?.applicable_goals ?? 0;
                const met = weekSummary?.met_goals ?? 0;
                const ratio = weekSummary?.completion_ratio ?? 0;
                const percent = toPercent(ratio);
                const weekRangeLabel = formatWeekRange(weekStart, weekEnd);

                return (
                  <Fragment key={weekStart}>
                    {weekDates.map((date) => {
                      const day = dayMap.get(date);
                      const parsed = parseDateInput(date);
                      const isOutsideMonth = parsed.getMonth() !== grid.monthIndex;
                      const isSelected = date === selectedDate;
                      const applicableGoals = day?.applicable_goals ?? 0;
                      const metGoals = day?.met_goals ?? 0;
                      const dayRatio = day?.completion_ratio ?? 0;
                      const dayPercent = toPercent(dayRatio);
                      const conditions = (day?.conditions ?? []).filter(
                        (condition) => condition.value,
                      );
                      const visibleConditions = conditions.slice(0, 3);
                      const extraCount = conditions.length - visibleConditions.length;
                      const dailyLabel =
                        applicableGoals > 0
                          ? `${metGoals}/${applicableGoals} daily`
                          : "No daily goals";

                      return (
                        <button
                          key={date}
                          className={`calendar-day${
                            isOutsideMonth ? " calendar-day--outside" : ""
                          }${isSelected ? " calendar-day--selected" : ""}`}
                          type="button"
                          onClick={() => {
                            setSelectedDate(date);
                            navigate("/today");
                          }}
                          aria-label={`Open ${dateFormatter.format(parsed)}`}
                        >
                          <div className="calendar-day__number">{parsed.getDate()}</div>
                          <div className="calendar-day__summary">
                            <span>{dailyLabel}</span>
                            <span className="calendar-day__percent">{dayPercent}%</span>
                          </div>
                          <div className="calendar-day__bar">
                            <span style={{ width: `${dayPercent}%` }} />
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
                    <div
                      className="calendar-week"
                      aria-label={`Week summary ${weekRangeLabel}`}
                    >
                      <div className="calendar-week__label">{weekRangeLabel}</div>
                      <div className="calendar-week__summary">
                        <span>
                          {applicable > 0 ? `${met}/${applicable} met` : "No weekly goals"}
                        </span>
                        <span className="calendar-week__percent">{percent}%</span>
                      </div>
                      <div className="calendar-week__bar">
                        <span style={{ width: `${percent}%` }} />
                      </div>
                    </div>
                  </Fragment>
                );
              })}
            </div>
            <div className="calendar-weekly-mobile" aria-label="Weekly goals">
              <div className="calendar-weekly-mobile__label">Weekly goals</div>
              {weeks.map((weekDates) => {
                const weekStart = weekDates[0];
                const weekEnd = weekDates[weekDates.length - 1] ?? weekStart;
                const weekSummary = weekMap.get(weekStart);
                const applicable = weekSummary?.applicable_goals ?? 0;
                const met = weekSummary?.met_goals ?? 0;
                const ratio = weekSummary?.completion_ratio ?? 0;
                const percent = toPercent(ratio);
                const weekRangeLabel = formatWeekRange(weekStart, weekEnd);

                return (
                  <details key={weekStart} className="calendar-weekly-mobile__item">
                    <summary>{`Week ${weekRangeLabel}`}</summary>
                    <div className="calendar-weekly-mobile__content">
                      <div className="calendar-weekly-mobile__summary">
                        <span>
                          {applicable > 0 ? `${met}/${applicable} met` : "No weekly goals"}
                        </span>
                        <span className="calendar-weekly-mobile__percent">{percent}%</span>
                      </div>
                      <div className="calendar-weekly-mobile__bar">
                        <span style={{ width: `${percent}%` }} />
                      </div>
                    </div>
                  </details>
                );
              })}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
