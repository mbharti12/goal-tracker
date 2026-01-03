import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getErrorMessage } from "../api/client";
import {
  createTag,
  createTagEvent,
  deleteTagEvent,
  upsertDayConditions,
  upsertDayNote,
  upsertDayRatings,
} from "../api/endpoints";
import type { DayGoalRatingRead, GoalStatus, TagEventRead, TagRead } from "../api/types";
import { useRefresh } from "../context/RefreshContext";
import { useSelectedDate } from "../context/SelectedDateContext";
import { useToast } from "../context/ToastContext";
import { useConditions } from "../hooks/useConditions";
import { useDay } from "../hooks/useDay";
import { useTags } from "../hooks/useTags";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { addDays, parseDateInput } from "../utils/date";

type BannerError = {
  message: string;
  retry?: () => void;
};

const formatTime = (value?: string | null) => {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
};

const statusLabels: Record<GoalStatus["status"], string> = {
  met: "Met",
  partial: "Partial",
  missed: "Missed",
  na: "N/A",
};

const progressWindowLabels: Record<GoalStatus["target_window"], string> = {
  day: "daily",
  week: "week to date",
  month: "month to date",
};

const groupLabels: Record<GoalStatus["target_window"], string> = {
  day: "Daily goals",
  week: "Weekly goals",
  month: "Monthly goals",
};

const groupEmptyLabels: Record<GoalStatus["target_window"], string> = {
  day: "No daily goals.",
  week: "No weekly goals.",
  month: "No monthly goals.",
};

const goalGroupOrder: GoalStatus["target_window"][] = ["day", "week", "month"];

const clampRating = (value: number) => Math.min(100, Math.max(1, value));

const mergeGoalRatings = (
  current: DayGoalRatingRead[] | undefined,
  updates: DayGoalRatingRead[],
) => {
  const merged = new Map<number, DayGoalRatingRead>();
  (current ?? []).forEach((rating) => merged.set(rating.goal_id, rating));
  updates.forEach((rating) => merged.set(rating.goal_id, rating));
  return Array.from(merged.values());
};

export default function Today() {
  const { selectedDate, setSelectedDate } = useSelectedDate();
  const [tagQuery, setTagQuery] = useState("");
  const [actionError, setActionError] = useState<BannerError | null>(null);
  const noteTimerRef = useRef<number | null>(null);
  const noteInitializedRef = useRef(false);
  const noteSaveFailedRef = useRef<string | null>(null);
  const ratingTimersRef = useRef<Map<number, number>>(new Map());
  const ratingInitializedRef = useRef(false);
  const { bumpRefreshToken } = useRefresh();
  const { pushToast } = useToast();

  const { day, setDay, loading: dayLoading, error: dayError, reload: reloadDay } =
    useDay(selectedDate);
  const {
    conditions,
    loading: conditionsLoading,
    error: conditionsError,
    reload: reloadConditions,
  } = useConditions();
  const { tags, setTags, loading: tagsLoading, error: tagsError, reload: reloadTags } =
    useTags({ includeInactive: true });

  const [noteDraft, setNoteDraft] = useState("");
  const [isSavingNote, setIsSavingNote] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const [showArchivedTags, setShowArchivedTags] = useState(false);
  const [ratingDrafts, setRatingDrafts] = useState<Record<number, number | null>>(
    {},
  );
  const [ratingPendingByGoal, setRatingPendingByGoal] = useState<
    Record<number, boolean>
  >({});

  const loadError = dayError ?? conditionsError ?? tagsError;
  const loadRetry = dayError
    ? reloadDay
    : conditionsError
      ? reloadConditions
      : tagsError
        ? reloadTags
        : undefined;
  const bannerError: BannerError | null =
    actionError ?? (loadError ? { message: loadError, retry: loadRetry } : null);

  useEffect(() => {
    setActionError(null);
    noteInitializedRef.current = false;
    noteSaveFailedRef.current = null;
    setNoteDraft("");
    setIsSavingNote(false);
    setLastSavedAt(null);
    if (noteTimerRef.current) {
      window.clearTimeout(noteTimerRef.current);
      noteTimerRef.current = null;
    }
    ratingInitializedRef.current = false;
    setRatingDrafts({});
    setRatingPendingByGoal({});
    ratingTimersRef.current.forEach((timer) => window.clearTimeout(timer));
    ratingTimersRef.current.clear();
  }, [selectedDate]);

  useEffect(() => {
    if (!day) {
      return;
    }
    if (!noteInitializedRef.current) {
      setNoteDraft(day.day_entry?.note ?? "");
      noteInitializedRef.current = true;
    }
    if (day.day_entry?.updated_at) {
      setLastSavedAt(day.day_entry.updated_at);
    }
  }, [day]);

  useEffect(() => {
    if (!day || ratingInitializedRef.current) {
      return;
    }
    const initialRatings: Record<number, number | null> = {};
    day.goal_ratings?.forEach((rating) => {
      initialRatings[rating.goal_id] = rating.rating;
    });
    setRatingDrafts(initialRatings);
    ratingInitializedRef.current = true;
  }, [day]);

  useEffect(() => {
    return () => {
      ratingTimersRef.current.forEach((timer) => window.clearTimeout(timer));
      ratingTimersRef.current.clear();
    };
  }, []);

  const displayDate = useMemo(() => {
    const date = parseDateInput(selectedDate);
    return new Intl.DateTimeFormat(undefined, {
      weekday: "long",
      month: "short",
      day: "numeric",
      year: "numeric",
    }).format(date);
  }, [selectedDate]);

  const sortedTags = useMemo(
    () => [...tags].sort((a, b) => a.name.localeCompare(b.name)),
    [tags],
  );
  const activeTags = useMemo(
    () => sortedTags.filter((tag) => tag.active),
    [sortedTags],
  );
  const pickerTags = showArchivedTags ? sortedTags : activeTags;
  const tagStatusById = useMemo(
    () => new Map(tags.map((tag) => [tag.id, tag.active])),
    [tags],
  );
  const trimmedQuery = tagQuery.trim();
  const normalizedQuery = trimmedQuery.toLowerCase();
  const matchedTag = useMemo(
    () => pickerTags.find((tag) => tag.name.toLowerCase() === normalizedQuery),
    [normalizedQuery, pickerTags],
  );
  const filteredTags = useMemo(() => {
    if (!normalizedQuery) {
      return pickerTags;
    }
    return pickerTags.filter((tag) =>
      tag.name.toLowerCase().includes(normalizedQuery),
    );
  }, [normalizedQuery, pickerTags]);
  const commonTags = useMemo(() => pickerTags.slice(0, 6), [pickerTags]);

  const conditionSelections = useMemo(() => {
    return conditions.map((condition) => {
      const stored = day?.conditions.find(
        (entry) => entry.condition_id === condition.id,
      );
      return { condition, value: stored?.value ?? false };
    });
  }, [conditions, day]);

  const savedRatingsByGoal = useMemo(() => {
    const ratings = new Map<number, number>();
    day?.goal_ratings?.forEach((rating) => {
      ratings.set(rating.goal_id, rating.rating);
    });
    return ratings;
  }, [day?.goal_ratings]);

  const parseRatingInput = useCallback((value: string) => {
    if (!value.trim()) {
      return null;
    }
    const parsed = Number(value);
    if (Number.isNaN(parsed)) {
      return null;
    }
    return clampRating(parsed);
  }, []);

  const refreshDerivedData = useCallback(() => {
    reloadDay();
    bumpRefreshToken();
  }, [bumpRefreshToken, reloadDay]);

  const handleToggleCondition = useCallback(
    async (conditionId: number) => {
      if (!day) {
        return;
      }

      const updatedConditions = conditionSelections.map(({ condition, value }) => ({
        condition_id: condition.id,
        name: condition.name,
        value: condition.id === conditionId ? !value : value,
      }));
      const previousConditions = day.conditions;

      setDay((current) =>
        current ? { ...current, conditions: updatedConditions } : current,
      );

      try {
        const response = await upsertDayConditions(selectedDate, {
          conditions: updatedConditions.map(({ condition_id, value }) => ({
            condition_id,
            value,
          })),
        });
        setDay((current) => (current ? { ...current, conditions: response } : current));
        setActionError(null);
        refreshDerivedData();
        pushToast({ type: "success", message: "Condition updated." });
      } catch (error) {
        setDay((current) =>
          current ? { ...current, conditions: previousConditions } : current,
        );
        setActionError({
          message: getErrorMessage(error),
          retry: () => handleToggleCondition(conditionId),
        });
        pushToast({ type: "error", message: "Failed to update condition." });
      }
    },
    [conditionSelections, day, pushToast, refreshDerivedData, selectedDate, setDay],
  );

  const handleAddTagEvent = useCallback(
    async (tag: TagRead) => {
      try {
        const event = await createTagEvent(selectedDate, { tag_id: tag.id, count: 1 });
        if (day) {
          setDay((current) =>
            current
              ? { ...current, tag_events: [event, ...current.tag_events] }
              : current,
          );
        }
        setActionError(null);
        refreshDerivedData();
        pushToast({ type: "success", message: "Tag event added." });
      } catch (error) {
        setActionError({
          message: getErrorMessage(error),
          retry: () => handleAddTagEvent(tag),
        });
        pushToast({ type: "error", message: "Failed to add tag event." });
      }
    },
    [day, pushToast, refreshDerivedData, selectedDate, setDay],
  );

  const handleCreateTagAndAdd = useCallback(
    async (name: string) => {
      const trimmed = name.trim();
      if (!trimmed) {
        return;
      }
      try {
        const created = await createTag({ name: trimmed });
        setTags((prev) => {
          const exists = prev.some((tag) => tag.id === created.id);
          if (exists) {
            return prev.map((tag) => (tag.id === created.id ? created : tag));
          }
          return [...prev, created];
        });
        setTagQuery("");
        await handleAddTagEvent(created);
      } catch (error) {
        setActionError({
          message: getErrorMessage(error),
          retry: () => handleCreateTagAndAdd(name),
        });
        pushToast({ type: "error", message: "Failed to create tag." });
      }
    },
    [handleAddTagEvent, pushToast, setTagQuery, setTags],
  );

  const handleDeleteTagEvent = useCallback(
    async (eventId: number) => {
      if (!day) {
        return;
      }
      const previousEvents = day.tag_events;
      setDay((current) =>
        current
          ? { ...current, tag_events: current.tag_events.filter((event) => event.id !== eventId) }
          : current,
      );
      try {
        await deleteTagEvent(eventId);
        setActionError(null);
        refreshDerivedData();
        pushToast({ type: "success", message: "Tag event deleted." });
      } catch (error) {
        setDay((current) => (current ? { ...current, tag_events: previousEvents } : current));
        setActionError({
          message: getErrorMessage(error),
          retry: () => handleDeleteTagEvent(eventId),
        });
        pushToast({ type: "error", message: "Failed to delete tag event." });
      }
    },
    [day, pushToast, refreshDerivedData, setDay],
  );

  const deleteTagEventAction = useAsyncAction(handleDeleteTagEvent);

  const saveRating = useCallback(
    async (goalId: number, rating: number) => {
      setRatingPendingByGoal((prev) => ({ ...prev, [goalId]: true }));
      try {
        const response = await upsertDayRatings(selectedDate, {
          ratings: [{ goal_id: goalId, rating }],
        });
        setDay((current) =>
          current
            ? {
                ...current,
                goal_ratings: mergeGoalRatings(current.goal_ratings, response),
              }
            : current,
        );
        setActionError(null);
        refreshDerivedData();
        pushToast({ type: "success", message: "Rating saved." });
      } catch (error) {
        const fallback = savedRatingsByGoal.get(goalId) ?? null;
        setRatingDrafts((prev) => ({ ...prev, [goalId]: fallback }));
        setActionError({
          message: getErrorMessage(error),
          retry: () => {
            setRatingDrafts((prev) => ({ ...prev, [goalId]: rating }));
            void saveRating(goalId, rating);
          },
        });
        pushToast({ type: "error", message: "Failed to save rating." });
      } finally {
        setRatingPendingByGoal((prev) => ({ ...prev, [goalId]: false }));
      }
    },
    [
      pushToast,
      refreshDerivedData,
      savedRatingsByGoal,
      selectedDate,
      setDay,
      setRatingPendingByGoal,
    ],
  );

  const handleRatingDraftChange = useCallback(
    (goalId: number, nextValue: number | null) => {
      setRatingDrafts((prev) => ({ ...prev, [goalId]: nextValue }));

      const existingTimer = ratingTimersRef.current.get(goalId);
      if (existingTimer) {
        window.clearTimeout(existingTimer);
        ratingTimersRef.current.delete(goalId);
      }

      if (nextValue === null) {
        return;
      }

      const savedValue = savedRatingsByGoal.get(goalId);
      if (savedValue === nextValue) {
        return;
      }

      const timer = window.setTimeout(() => {
        ratingTimersRef.current.delete(goalId);
        void saveRating(goalId, nextValue);
      }, 800);
      ratingTimersRef.current.set(goalId, timer);
    },
    [saveRating, savedRatingsByGoal],
  );

  const saveNote = useCallback(
    async (nextNote: string) => {
      setIsSavingNote(true);
      try {
        const entry = await upsertDayNote(selectedDate, { note: nextNote });
        setDay((current) => (current ? { ...current, day_entry: entry } : current));
        setLastSavedAt(entry.updated_at);
        noteSaveFailedRef.current = null;
        setActionError(null);
        refreshDerivedData();
        pushToast({ type: "success", message: "Note saved." });
      } catch (error) {
        noteSaveFailedRef.current = nextNote;
        setActionError({
          message: getErrorMessage(error),
          retry: () => saveNote(nextNote),
        });
        pushToast({ type: "error", message: "Failed to save note." });
      } finally {
        setIsSavingNote(false);
      }
    },
    [pushToast, refreshDerivedData, selectedDate, setDay],
  );

  useEffect(() => {
    if (!noteInitializedRef.current || !day) {
      return;
    }
    if (noteSaveFailedRef.current === noteDraft) {
      return;
    }
    if (noteDraft === (day.day_entry?.note ?? "")) {
      return;
    }
    if (noteTimerRef.current) {
      window.clearTimeout(noteTimerRef.current);
    }
    noteTimerRef.current = window.setTimeout(() => {
      saveNote(noteDraft);
    }, 800);
    return () => {
      if (noteTimerRef.current) {
        window.clearTimeout(noteTimerRef.current);
      }
    };
  }, [day, noteDraft, saveNote]);

  const orderedEvents = useMemo(() => {
    if (!day?.tag_events) {
      return [];
    }
    return [...day.tag_events].sort((a, b) => {
      const aTime = a.ts ? Date.parse(a.ts) : 0;
      const bTime = b.ts ? Date.parse(b.ts) : 0;
      if (aTime && bTime) {
        return bTime - aTime;
      }
      return b.id - a.id;
    });
  }, [day?.tag_events]);

  const canAddTagEvent = Boolean(matchedTag) && !dayLoading;
  const canCreateTag = trimmedQuery.length > 0 && !matchedTag && !tagsLoading;
  const emptyTagsLabel = showArchivedTags ? "No tags yet." : "No active tags yet.";
  const noteStatus = isSavingNote ? "Saving..." : lastSavedAt ? "Saved" : "Not saved yet";
  const lastSavedLabel = lastSavedAt ? formatTime(lastSavedAt) : null;

  const goals = day?.goals ?? [];
  const groupedGoals = useMemo(() => {
    const groups: Record<GoalStatus["target_window"], GoalStatus[]> = {
      day: [],
      week: [],
      month: [],
    };

    goals.forEach((goal) => {
      groups[goal.target_window].push(goal);
    });

    return goalGroupOrder.map((targetWindow) => ({
      targetWindow,
      label: groupLabels[targetWindow],
      emptyLabel: groupEmptyLabels[targetWindow],
      goals: groups[targetWindow],
    }));
  }, [goals]);

  return (
    <section className="page today-page">
      {bannerError && (
        <div className="error-banner" role="alert">
          <div className="error-banner__title">Something went wrong</div>
          <div className="error-banner__body">{bannerError.message}</div>
          {bannerError.retry && (
            <div className="error-banner__actions">
              <button
                className="action-button action-button--ghost"
                type="button"
                onClick={() => {
                  setActionError(null);
                  bannerError.retry?.();
                }}
              >
                Retry
              </button>
            </div>
          )}
        </div>
      )}

      <div className="card today-header">
        <div>
          <div className="today-header__label">Day detail</div>
          <div className="today-header__value">{displayDate}</div>
        </div>
        <div className="date-nav">
          <button
            className="icon-button"
            type="button"
            onClick={() => setSelectedDate((prev) => addDays(prev, -1))}
            aria-label="Previous day"
          >
            &#8592;
          </button>
          <input
            className="field field--compact"
            type="date"
            value={selectedDate}
            onChange={(event) => {
              if (event.target.value) {
                setSelectedDate(event.target.value);
              }
            }}
            aria-label="Select date"
          />
          <button
            className="icon-button"
            type="button"
            onClick={() => setSelectedDate((prev) => addDays(prev, 1))}
            aria-label="Next day"
          >
            &#8594;
          </button>
        </div>
      </div>

      <div className="today-grid">
        <div className="card">
          <h2>Conditions</h2>
          {conditionsLoading || dayLoading ? (
            <div className="status status--loading">Loading conditions...</div>
          ) : conditions.length === 0 ? (
            <div className="empty-state">No conditions yet.</div>
          ) : (
            <div className="chip-row">
              {conditionSelections.map(({ condition, value }) => (
                <button
                  key={condition.id}
                  className={`toggle-chip ${value ? "toggle-chip--active" : ""}`}
                  type="button"
                  onClick={() => handleToggleCondition(condition.id)}
                  aria-pressed={value}
                >
                  {condition.name}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <h2>Quick add tags</h2>
          <div className="tag-search">
            <input
              className="field"
              type="text"
              value={tagQuery}
              onChange={(event) => setTagQuery(event.target.value)}
              placeholder="Search tags"
            />
            <button
              className="action-button action-button--primary"
              type="button"
              onClick={() => {
                if (matchedTag) {
                  handleAddTagEvent(matchedTag);
                  setTagQuery("");
                }
              }}
              disabled={!canAddTagEvent}
            >
              Add tag event
            </button>
            <button
              className="action-button"
              type="button"
              onClick={() => handleCreateTagAndAdd(trimmedQuery)}
              disabled={!canCreateTag}
            >
              Create tag & add
            </button>
          </div>
          <div className="tag-filter-row">
            <label className="option-card option-card--compact">
              <input
                type="checkbox"
                checked={showArchivedTags}
                onChange={(event) => setShowArchivedTags(event.target.checked)}
              />
              <span>Show archived tags</span>
            </label>
          </div>

          {tagsLoading ? (
            <div className="status status--loading">Loading tags...</div>
          ) : pickerTags.length === 0 ? (
            <div className="empty-state">{emptyTagsLabel}</div>
          ) : (
            <>
              <div className="quick-tags">
                {commonTags.map((tag) => (
                  <button
                    key={tag.id}
                    className="quick-tag"
                    type="button"
                    onClick={() => handleAddTagEvent(tag)}
                  >
                    <span>{tag.name}</span>
                    <span className="quick-tag__count">+1</span>
                  </button>
                ))}
              </div>
              <div className="tag-list">
                {filteredTags.map((tag) => (
                  <div key={tag.id} className="tag-row">
                    <div className="tag-row__name">
                      {tag.name}
                      {!tag.active && (
                        <span className="tag-badge tag-badge--archived">
                          Archived
                        </span>
                      )}
                    </div>
                    <div className="tag-row__actions">
                      <button
                        className="action-button action-button--ghost"
                        type="button"
                        onClick={() => handleAddTagEvent(tag)}
                      >
                        Add
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="card">
          <h2>Goals progress</h2>
          {dayLoading ? (
            <div className="status status--loading">Loading goals...</div>
          ) : goals.length === 0 ? (
            <div className="empty-state">No goal progress for this day.</div>
          ) : (
            <div className="goal-group-list">
              {groupedGoals.map((group) => (
                <div key={group.targetWindow} className="goal-group">
                  <div className="goal-group__title">{group.label}</div>
                  {group.goals.length === 0 ? (
                    <div className="empty-state">{group.emptyLabel}</div>
                  ) : (
                    <div className="goal-list">
                      {group.goals.map((goal: GoalStatus) => (
                        <div key={goal.goal_id} className="goal-row">
                          <div className="goal-meta">
                            <div className="goal-name">{goal.goal_name}</div>
                            <div className="goal-progress">
                              {goal.scoring_mode === "rating" ? (
                                <>
                                  avg {goal.progress.toFixed(1)} / {goal.target}{" "}
                                  <span className="goal-window">
                                    ({goal.samples}/{goal.window_days} rated,{" "}
                                    {progressWindowLabels[goal.target_window]})
                                  </span>
                                </>
                              ) : (
                                <>
                                  {goal.progress}/{goal.target}{" "}
                                  <span className="goal-window">
                                    {progressWindowLabels[goal.target_window]}
                                  </span>
                                </>
                              )}
                            </div>
                          </div>
                          <div className="goal-actions">
                            {goal.scoring_mode === "rating" && (
                              <div
                                className="goal-rating"
                                aria-busy={Boolean(ratingPendingByGoal[goal.goal_id])}
                              >
                                <input
                                  className="field field--compact goal-rating__input"
                                  type="number"
                                  min={1}
                                  max={100}
                                  step={1}
                                  inputMode="numeric"
                                  value={ratingDrafts[goal.goal_id] ?? ""}
                                  onChange={(event) => {
                                    const nextValue = parseRatingInput(
                                      event.target.value,
                                    );
                                    handleRatingDraftChange(goal.goal_id, nextValue);
                                  }}
                                  onBlur={() => {
                                    if (ratingDrafts[goal.goal_id] !== null) {
                                      return;
                                    }
                                    const savedValue = savedRatingsByGoal.get(goal.goal_id);
                                    if (savedValue === undefined) {
                                      return;
                                    }
                                    setRatingDrafts((prev) => ({
                                      ...prev,
                                      [goal.goal_id]: savedValue,
                                    }));
                                  }}
                                  placeholder="1-100"
                                  aria-label={`Rating for ${goal.goal_name}`}
                                  disabled={
                                    dayLoading ||
                                    Boolean(ratingPendingByGoal[goal.goal_id])
                                  }
                                />
                                {ratingPendingByGoal[goal.goal_id] && (
                                  <span className="goal-rating__status">Saving...</span>
                                )}
                              </div>
                            )}
                            <div className={`goal-status goal-status--${goal.status}`}>
                              {statusLabels[goal.status]}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card today-span-2">
          <h2>Daily note</h2>
          <div className="note-meta">
            <span className="note-status">{noteStatus}</span>
            {lastSavedLabel && (
              <span className="note-time">Last saved {lastSavedLabel}</span>
            )}
          </div>
          <textarea
            className="field note-textarea"
            value={noteDraft}
            onChange={(event) => setNoteDraft(event.target.value)}
            placeholder="Capture reflections, friction, or wins."
            disabled={dayLoading}
          />
        </div>

        <div className="card today-span-2">
          <h2>Tag events</h2>
          {dayLoading ? (
            <div className="status status--loading">Loading events...</div>
          ) : orderedEvents.length === 0 ? (
            <div className="empty-state">No tag events yet.</div>
          ) : (
            <div className="event-list">
              {orderedEvents.map((event: TagEventRead) => (
                <div key={event.id} className="event-row">
                  <div className="event-meta">
                    <div className="event-name">
                      <span>{event.tag_name}</span>
                      {tagStatusById.get(event.tag_id) === false && (
                        <span className="tag-badge tag-badge--archived">
                          Archived
                        </span>
                      )}
                    </div>
                    {event.ts && (
                      <div className="event-time">{formatTime(event.ts)}</div>
                    )}
                  </div>
                  <div className="event-actions">
                    <span className="event-count">x{event.count}</span>
                    <button
                      className="action-button action-button--ghost"
                      type="button"
                      onClick={() => {
                        void deleteTagEventAction.run(event.id);
                      }}
                      disabled={deleteTagEventAction.pending}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
