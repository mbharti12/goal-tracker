import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, getErrorMessage } from "../api/client";
import {
  compareTrends,
  getCalendar,
  getDay,
  getLlmHealth,
  reviewFilter,
  reviewQuery,
} from "../api/endpoints";
import type {
  LlmHealthResponse,
  ReviewDebug,
  TrendBucket,
  TrendCompareResponse,
} from "../api/types";
import MultiTrendChart from "../components/MultiTrendChart";
import { useRefresh } from "../context/RefreshContext";
import { useConditions } from "../hooks/useConditions";
import { useGoals } from "../hooks/useGoals";
import { addDays, formatDateInput, listDateRange, parseDateInput } from "../utils/date";

const DOW_OPTIONS = [
  { value: "mon", label: "Mon" },
  { value: "tue", label: "Tue" },
  { value: "wed", label: "Wed" },
  { value: "thu", label: "Thu" },
  { value: "fri", label: "Fri" },
  { value: "sat", label: "Sat" },
  { value: "sun", label: "Sun" },
];

const DOW_BY_INDEX = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
const DEFAULT_OLLAMA_MODEL = "llama3.2:1b";
const DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434";
const TREND_BUCKETS: Array<{ value: TrendBucket; label: string }> = [
  { value: "day", label: "Day" },
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
];

type LlmHealthState = {
  loading: boolean;
  data: LlmHealthResponse | null;
  error: string | null;
};

type OllamaHelpProps = {
  model: string;
};

const OllamaHelp = ({ model }: OllamaHelpProps) => (
  <div className="review-help">
    <div>To enable the local model:</div>
    <ul>
      <li>
        Install Ollama: <code>brew install ollama</code>
      </li>
      <li>
        Start the server: <code>ollama serve</code>
      </li>
      <li>
        Pull the model: <code>ollama pull {model}</code>
      </li>
    </ul>
  </div>
);

export default function Review() {
  const todayLabel = formatDateInput(new Date());
  const [startDate, setStartDate] = useState(() => addDays(todayLabel, -13));
  const [endDate, setEndDate] = useState(() => todayLabel);
  const [daysOfWeek, setDaysOfWeek] = useState<string[]>([]);
  const [conditionsAll, setConditionsAll] = useState<number[]>([]);
  const [conditionsAny, setConditionsAny] = useState<number[]>([]);
  const [goalIds, setGoalIds] = useState<number[]>([]);
  const [manualPrompt, setManualPrompt] = useState("");

  const [previewDates, setPreviewDates] = useState<string[]>([]);
  const [previewMeta, setPreviewMeta] = useState<{ source: string; truncated: boolean } | null>(
    null,
  );
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [trendBucket, setTrendBucket] = useState<TrendBucket>("week");
  const [trendData, setTrendData] = useState<TrendCompareResponse | null>(null);
  const [trendLoading, setTrendLoading] = useState(false);
  const [trendError, setTrendError] = useState<string | null>(null);
  const [trendReloadToken, setTrendReloadToken] = useState(0);

  const [aiPrompt, setAiPrompt] = useState("");
  const [aiAnswer, setAiAnswer] = useState<string | null>(null);
  const [aiDebug, setAiDebug] = useState<ReviewDebug | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [llmHealth, setLlmHealth] = useState<LlmHealthState>({
    loading: true,
    data: null,
    error: null,
  });
  const [showOllamaHelp, setShowOllamaHelp] = useState(false);
  const [lastQueryLabel, setLastQueryLabel] = useState<string | null>(null);
  const { refreshToken } = useRefresh();
  const lastRefreshTokenRef = useRef(refreshToken);

  const {
    conditions,
    loading: conditionsLoading,
    error: conditionsError,
    reload: reloadConditions,
  } = useConditions();
  const { goals, loading: goalsLoading, error: goalsError, reload: reloadGoals } =
    useGoals();

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const data = await getLlmHealth();
        if (!cancelled) {
          setLlmHealth({ loading: false, data, error: null });
        }
      } catch (error) {
        if (!cancelled) {
          setLlmHealth({
            loading: false,
            data: null,
            error: getErrorMessage(error),
          });
        }
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, []);

  const sortedConditions = useMemo(
    () => [...conditions].sort((a, b) => a.name.localeCompare(b.name)),
    [conditions],
  );
  const sortedGoals = useMemo(
    () => [...goals].sort((a, b) => a.name.localeCompare(b.name)),
    [goals],
  );

  const conditionNameMap = useMemo(
    () => new Map(conditions.map((condition) => [condition.id, condition.name])),
    [conditions],
  );
  const goalNameMap = useMemo(
    () => new Map(goals.map((goal) => [goal.id, goal.name])),
    [goals],
  );

  const conditionsAllNames = useMemo(
    () =>
      conditionsAll
        .map((id) => conditionNameMap.get(id))
        .filter((name): name is string => Boolean(name)),
    [conditionNameMap, conditionsAll],
  );
  const conditionsAnyNames = useMemo(
    () =>
      conditionsAny
        .map((id) => conditionNameMap.get(id))
        .filter((name): name is string => Boolean(name)),
    [conditionNameMap, conditionsAny],
  );
  const goalNames = useMemo(
    () =>
      goalIds.map((id) => goalNameMap.get(id)).filter((name): name is string => Boolean(name)),
    [goalIds, goalNameMap],
  );

  const filterPayload = useMemo(
    () => ({
      start_date: startDate,
      end_date: endDate,
      days_of_week: daysOfWeek.length > 0 ? daysOfWeek : null,
      conditions_all: conditionsAllNames.length > 0 ? conditionsAllNames : null,
      conditions_any: conditionsAnyNames.length > 0 ? conditionsAnyNames : null,
      goals: goalNames.length > 0 ? goalNames : null,
    }),
    [conditionsAllNames, conditionsAnyNames, daysOfWeek, endDate, goalNames, startDate],
  );

  const rangeValid = useMemo(() => {
    const start = parseDateInput(startDate);
    const end = parseDateInput(endDate);
    return start <= end;
  }, [endDate, startDate]);

  const toggleSelection = useCallback(
    (values: string[], value: string) =>
      values.includes(value) ? values.filter((item) => item !== value) : [...values, value],
    [],
  );
  const toggleId = useCallback(
    (values: number[], id: number) =>
      values.includes(id) ? values.filter((item) => item !== id) : [...values, id],
    [],
  );

  const buildFilterHint = useCallback((payload: typeof filterPayload) => {
    const parts = [`start_date=${payload.start_date}`, `end_date=${payload.end_date}`];
    if (payload.days_of_week?.length) {
      parts.push(`days_of_week=${payload.days_of_week.join(",")}`);
    }
    if (payload.conditions_all?.length) {
      parts.push(`conditions_all=${payload.conditions_all.join(",")}`);
    }
    if (payload.conditions_any?.length) {
      parts.push(`conditions_any=${payload.conditions_any.join(",")}`);
    }
    if (payload.goals?.length) {
      parts.push(`goals=${payload.goals.join(",")}`);
    }
    return parts.join("; ");
  }, []);

  const handlePreview = useCallback(async () => {
    if (!rangeValid) {
      setPreviewError("Start date must be on or before end date.");
      return;
    }

    setPreviewLoading(true);
    setPreviewError(null);
    setPreviewDates([]);
    setPreviewMeta(null);

    try {
      const response = await reviewFilter(filterPayload);
      const dates = response.context.days.map((day) => day.date);
      setPreviewDates(dates);
      setPreviewMeta({ source: "/review/filter", truncated: response.context.truncated });
    } catch (error) {
      const errorValue = error as unknown;
      if (
        errorValue instanceof ApiError &&
        [404, 405, 501].includes(errorValue.status)
      ) {
        try {
          const calendar = await getCalendar(filterPayload.start_date, filterPayload.end_date);
          const calendarMap = new Map(calendar.map((day) => [day.date, day]));
          let dates = listDateRange(filterPayload.start_date, filterPayload.end_date);

          if (filterPayload.days_of_week?.length) {
            dates = dates.filter((date) => {
              const dayValue = DOW_BY_INDEX[parseDateInput(date).getDay()];
              return filterPayload.days_of_week?.includes(dayValue);
            });
          }

          if (filterPayload.conditions_all?.length || filterPayload.conditions_any?.length) {
            dates = dates.filter((date) => {
              const day = calendarMap.get(date);
              const trueConditions = (day?.conditions ?? []).map(
                (condition) => condition.name,
              );
              if (filterPayload.conditions_all?.length) {
                if (
                  !filterPayload.conditions_all.every((condition) =>
                    trueConditions.includes(condition),
                  )
                ) {
                  return false;
                }
              }
              if (filterPayload.conditions_any?.length) {
                if (
                  !filterPayload.conditions_any.some((condition) =>
                    trueConditions.includes(condition),
                  )
                ) {
                  return false;
                }
              }
              return true;
            });
          }

          if (dates.length > 0) {
            await Promise.all(dates.map((date) => getDay(date)));
          }

          setPreviewDates(dates);
          setPreviewMeta({ source: "calendar/day fallback", truncated: false });
        } catch (fallbackError) {
          setPreviewError(getErrorMessage(fallbackError));
        }
      } else {
        setPreviewError(getErrorMessage(error));
      }
    } finally {
      setPreviewLoading(false);
    }
  }, [filterPayload, rangeValid]);

  useEffect(() => {
    if (refreshToken === lastRefreshTokenRef.current) {
      return;
    }
    if (previewLoading) {
      return;
    }
    lastRefreshTokenRef.current = refreshToken;
    if (!previewMeta && previewDates.length === 0) {
      return;
    }
    handlePreview();
  }, [handlePreview, previewDates.length, previewLoading, previewMeta, refreshToken]);

  useEffect(() => {
    if (!rangeValid || goalIds.length < 2) {
      setTrendData(null);
      setTrendError(null);
      setTrendLoading(false);
      return;
    }
    let cancelled = false;
    const load = async () => {
      setTrendLoading(true);
      setTrendError(null);
      try {
        const data = await compareTrends(goalIds, startDate, endDate, trendBucket);
        if (!cancelled) {
          setTrendData(data);
          setTrendLoading(false);
        }
      } catch (error) {
        if (!cancelled) {
          setTrendError(getErrorMessage(error));
          setTrendLoading(false);
        }
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [endDate, goalIds, rangeValid, startDate, trendBucket, trendReloadToken]);

  const runQuery = useCallback(async (prompt: string, label: string) => {
    const trimmed = prompt.trim();
    if (!trimmed) {
      return;
    }
    setAiLoading(true);
    setAiError(null);
    setShowOllamaHelp(false);
    try {
      const response = await reviewQuery({ prompt: trimmed });
      setAiAnswer(response.answer);
      setAiDebug(response.debug);
      setLastQueryLabel(label);
    } catch (error) {
      setAiAnswer(null);
      setAiDebug(null);
      setAiError(getErrorMessage(error));
      if (error instanceof ApiError && error.status === 503) {
        setShowOllamaHelp(true);
      }
    } finally {
      setAiLoading(false);
    }
  }, []);

  const handleManualSummary = useCallback(() => {
    if (!rangeValid) {
      setAiError("Start date must be on or before end date.");
      return;
    }
    const promptBase = manualPrompt.trim() || "Summarize the selected days.";
    const hint = buildFilterHint(filterPayload);
    const fullPrompt = hint ? `${promptBase}\n\nFilters: ${hint}` : promptBase;
    runQuery(fullPrompt, "Manual filters");
  }, [buildFilterHint, filterPayload, manualPrompt, rangeValid, runQuery]);

  const handlePromptOnly = useCallback(() => {
    runQuery(aiPrompt, "Prompt-only");
  }, [aiPrompt, runQuery]);

  const handleTrendRetry = useCallback(() => {
    setTrendReloadToken((prev) => prev + 1);
  }, []);

  const canSubmit = rangeValid && !previewLoading;
  const previewLabel =
    previewDates.length > 0
      ? `${previewDates.length} day${previewDates.length === 1 ? "" : "s"} included`
      : "No dates selected yet.";

  const llmModel = llmHealth.data?.model ?? DEFAULT_OLLAMA_MODEL;
  const llmBaseUrl = llmHealth.data?.base_url ?? DEFAULT_OLLAMA_BASE_URL;

  const renderLlmStatus = () => {
    if (llmHealth.loading) {
      return <div className="status status--loading">Checking LLM...</div>;
    }

    if (llmHealth.error) {
      return (
        <div className="status status--error" role="alert">
          <span>LLM status unavailable.</span>
          <span className="status-detail">{llmHealth.error}</span>
        </div>
      );
    }

    if (llmHealth.data?.reachable) {
      return (
        <div className="status status--ok">
          <span>LLM ready.</span>
          <span className="status-detail">Model: {llmModel}</span>
          <span className="status-detail">Ollama: {llmBaseUrl}</span>
        </div>
      );
    }

    return (
      <div className="status status--error" role="alert">
        <span>Ollama not running.</span>
        {llmHealth.data?.error && (
          <span className="status-detail">{llmHealth.data.error}</span>
        )}
        <OllamaHelp model={llmModel} />
      </div>
    );
  };

  const debugPlanText = useMemo(
    () => (aiDebug ? JSON.stringify(aiDebug.plan, null, 2) : ""),
    [aiDebug],
  );

  const formatCorrelation = useCallback(
    (value: number | null) => (value === null ? "—" : value.toFixed(2)),
    [],
  );

  const lookupGoalName = useCallback(
    (goalId: number) => goalNameMap.get(goalId) ?? `Goal ${goalId}`,
    [goalNameMap],
  );

  return (
    <section className="page review-page">
      <div className="review-layout">
        <div className="card review-panel">
          <h2>Manual filters</h2>
          <p>Curate a specific slice of days before asking for insights.</p>

          <div className="field-group">
            <label className="field-label">Date range</label>
            <div className="field-row">
              <input
                className="field"
                type="date"
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
              />
              <input
                className="field"
                type="date"
                value={endDate}
                onChange={(event) => setEndDate(event.target.value)}
              />
            </div>
            {!rangeValid && (
              <div className="field-error">Start date must be on or before end date.</div>
            )}
          </div>

          <div className="field-group">
            <label className="field-label">Days of week</label>
            <div className="chip-row">
              {DOW_OPTIONS.map((option) => {
                const isActive = daysOfWeek.includes(option.value);
                return (
                  <button
                    key={option.value}
                    type="button"
                    className={`toggle-chip${isActive ? " toggle-chip--active" : ""}`}
                    onClick={() =>
                      setDaysOfWeek((prev) => toggleSelection(prev, option.value))
                    }
                    aria-pressed={isActive}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="field-group">
            <label className="field-label">Conditions (all must be true)</label>
            {conditionsLoading ? (
              <div className="status status--loading">Loading conditions...</div>
            ) : conditionsError ? (
              <div className="status status--error" role="alert">
                <div>Could not load conditions. {conditionsError}</div>
                <button
                  className="action-button"
                  type="button"
                  onClick={reloadConditions}
                >
                  Retry
                </button>
              </div>
            ) : sortedConditions.length === 0 ? (
              <div className="empty-state">No conditions yet.</div>
            ) : (
              <div className="chip-row">
                {sortedConditions.map((condition) => {
                  const isActive = conditionsAll.includes(condition.id);
                  return (
                    <button
                      key={condition.id}
                      type="button"
                      className={`toggle-chip${isActive ? " toggle-chip--active" : ""}`}
                      onClick={() =>
                        setConditionsAll((prev) => toggleId(prev, condition.id))
                      }
                      aria-pressed={isActive}
                    >
                      {condition.name}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="field-group">
            <label className="field-label">Conditions (any true)</label>
            {conditionsLoading ? (
              <div className="status status--loading">Loading conditions...</div>
            ) : conditionsError ? (
              <div className="status status--error" role="alert">
                <div>Could not load conditions. {conditionsError}</div>
                <button
                  className="action-button"
                  type="button"
                  onClick={reloadConditions}
                >
                  Retry
                </button>
              </div>
            ) : sortedConditions.length === 0 ? (
              <div className="empty-state">No conditions yet.</div>
            ) : (
              <div className="chip-row">
                {sortedConditions.map((condition) => {
                  const isActive = conditionsAny.includes(condition.id);
                  return (
                    <button
                      key={condition.id}
                      type="button"
                      className={`toggle-chip${isActive ? " toggle-chip--active" : ""}`}
                      onClick={() =>
                        setConditionsAny((prev) => toggleId(prev, condition.id))
                      }
                      aria-pressed={isActive}
                    >
                      {condition.name}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="field-group">
            <label className="field-label">Goals focus</label>
            <div className="field-hint">
              Goals refine the summary focus and do not change which dates are included.
            </div>
            {goalsLoading ? (
              <div className="status status--loading">Loading goals...</div>
            ) : goalsError ? (
              <div className="status status--error" role="alert">
                <div>Could not load goals. {goalsError}</div>
                <button className="action-button" type="button" onClick={reloadGoals}>
                  Retry
                </button>
              </div>
            ) : sortedGoals.length === 0 ? (
              <div className="empty-state">No goals yet.</div>
            ) : (
              <div className="chip-row">
                {sortedGoals.map((goal) => {
                  const isActive = goalIds.includes(goal.id);
                  return (
                    <button
                      key={goal.id}
                      type="button"
                      className={`toggle-chip${isActive ? " toggle-chip--active" : ""}`}
                      onClick={() => setGoalIds((prev) => toggleId(prev, goal.id))}
                      aria-pressed={isActive}
                    >
                      {goal.name}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="field-group">
            <label className="field-label" htmlFor="manual-prompt">
              Summary prompt (optional)
            </label>
            <textarea
              id="manual-prompt"
              className="field"
              rows={3}
              value={manualPrompt}
              onChange={(event) => setManualPrompt(event.target.value)}
              placeholder="Summarize the patterns, wins, and blockers in this range."
            />
          </div>

          <div className="review-actions">
            <button
              className="action-button"
              type="button"
              onClick={handlePreview}
              disabled={!canSubmit}
            >
              {previewLoading ? "Previewing..." : "Preview context"}
            </button>
            <button
              className="action-button action-button--primary"
              type="button"
              onClick={handleManualSummary}
              disabled={!rangeValid || aiLoading}
            >
              {aiLoading ? "Summarizing..." : "Summarize with AI"}
            </button>
          </div>

          {previewError && (
            <div className="status status--error" role="alert">
              {previewError}
            </div>
          )}
          {previewLoading ? (
            <div className="status status--loading">Preparing preview...</div>
          ) : (
            <div className="review-preview">
              <div className="review-preview__summary">
                <div className="review-preview__count">{previewLabel}</div>
                {previewMeta?.truncated && (
                  <div className="field-hint">Preview truncated to keep it light.</div>
                )}
                {previewMeta?.source && (
                  <div className="field-hint">Source: {previewMeta.source}</div>
                )}
              </div>
              {previewDates.length > 0 && (
                <div className="review-preview__list">
                  {previewDates.map((date) => (
                    <span key={date} className="review-date-chip">
                      {date}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="card review-panel">
          <h2>Prompt-only AI</h2>
          <p>Ask with a single sentence and let the assistant plan the query.</p>
          <div className="field-group">
            <label className="field-label" htmlFor="prompt-only">
              Prompt
            </label>
            <textarea
              id="prompt-only"
              className="field"
              rows={4}
              value={aiPrompt}
              onChange={(event) => setAiPrompt(event.target.value)}
              placeholder="How did I do over the past 14 days when with_family?"
            />
          </div>
          <div className="review-actions">
            <button
              className="action-button action-button--primary"
              type="button"
              onClick={handlePromptOnly}
              disabled={!aiPrompt.trim() || aiLoading}
            >
              {aiLoading ? "Working..." : "Ask AI"}
            </button>
          </div>
        </div>
      </div>

      <div className="card review-trends">
        <div className="review-trends__header">
          <div>
            <h2>Trends</h2>
            <p>Compare momentum across the selected goals.</p>
          </div>
          <div className="review-trends__bucket">
            <div className="field-label">Bucket</div>
            <div className="chip-row">
              {TREND_BUCKETS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={`toggle-chip${
                    trendBucket === option.value ? " toggle-chip--active" : ""
                  }`}
                  onClick={() => setTrendBucket(option.value)}
                  aria-pressed={trendBucket === option.value}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {goalIds.length < 2 ? (
          <div className="empty-state">Select at least two goals to compare trends.</div>
        ) : !rangeValid ? (
          <div className="status status--error" role="alert">
            Fix the date range to load trend comparisons.
          </div>
        ) : (
          <>
            {trendError && (
              <div className="status status--error" role="alert">
                <div>Couldn’t load trends. {trendError}</div>
                <button className="action-button" type="button" onClick={handleTrendRetry}>
                  Retry
                </button>
              </div>
            )}

            <MultiTrendChart series={trendData?.series ?? []} loading={trendLoading} />

            <div className="trend-comparisons">
              <div className="trend-comparisons__title">Correlations</div>
              {trendData?.comparisons?.length ? (
                <div className="trend-comparisons__list">
                  {trendData.comparisons.map((item) => (
                    <div
                      key={`${item.goal_id_a}-${item.goal_id_b}`}
                      className="trend-comparisons__row"
                    >
                      <span>
                        {lookupGoalName(item.goal_id_a)} vs{" "}
                        {lookupGoalName(item.goal_id_b)}
                      </span>
                      <span>r={formatCorrelation(item.correlation)}</span>
                      <span>n={item.n}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="trend-comparisons__empty">
                  No comparable samples yet.
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <div className="card review-output">
        <h2>AI response</h2>
        {renderLlmStatus()}
        {aiLoading ? (
          <div className="status status--loading">Waiting for AI response...</div>
        ) : aiError ? (
          <div className="status status--error" role="alert">
            <div>{aiError}</div>
            {showOllamaHelp && (
              <OllamaHelp model={llmModel} />
            )}
          </div>
        ) : aiAnswer ? (
          <div className="review-output__body">
            {lastQueryLabel && (
              <div className="review-output__label">Source: {lastQueryLabel}</div>
            )}
            <div className="review-answer">{aiAnswer}</div>
          </div>
        ) : (
          <div className="empty-state">Run a query to see the AI summary here.</div>
        )}

        <details className="debug-panel">
          <summary>Debug details</summary>
          {aiDebug ? (
            <div className="debug-grid">
              <div>
                <div className="debug-label">Plan</div>
                <pre className="debug-block">{debugPlanText}</pre>
              </div>
              <div className="debug-meta">
                <div>Days included: {aiDebug.days_included}</div>
                <div>Truncated: {aiDebug.truncated ? "Yes" : "No"}</div>
                <div>
                  Range: {aiDebug.date_range.start} to {aiDebug.date_range.end}
                </div>
              </div>
            </div>
          ) : (
            <div className="empty-state">No debug data yet.</div>
          )}
        </details>
      </div>
    </section>
  );
}
