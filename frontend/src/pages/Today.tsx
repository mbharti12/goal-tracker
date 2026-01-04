import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getErrorMessage } from "../api/client";
import {
  createTag,
  createTagEvent,
  deleteTagEvent,
  getTagImpacts,
  upsertDayConditions,
  upsertDayNote,
  upsertDayRatings,
} from "../api/endpoints";
import type {
  DayGoalRatingRead,
  GoalStatus,
  TagEventRead,
  TagImpactRead,
  TagRead,
} from "../api/types";
import { useRefresh } from "../context/RefreshContext";
import { useSelectedDate } from "../context/SelectedDateContext";
import { useToast } from "../context/ToastContext";
import { useConditions } from "../hooks/useConditions";
import { useDay } from "../hooks/useDay";
import { useTags } from "../hooks/useTags";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { addDays, parseDateInput } from "../utils/date";
import {
  buildTagCategoryTabs,
  DEFAULT_TAG_CATEGORIES,
  normalizeTagCategory,
} from "../utils/tags";

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
const impactCountOptions = [1, 2, 3];
const customCategoryValue = "__custom__";

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
  const [showTagSearch, setShowTagSearch] = useState(false);
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
  const [selectedCategory, setSelectedCategory] = useState<string>(
    DEFAULT_TAG_CATEGORIES[0],
  );
  const [newTagCategory, setNewTagCategory] = useState<string>("Other");
  const [customTagCategory, setCustomTagCategory] = useState("");
  const [tagImpacts, setTagImpacts] = useState<TagImpactRead[]>([]);
  const [tagImpactsLoading, setTagImpactsLoading] = useState(false);
  const [tagImpactsError, setTagImpactsError] = useState<string | null>(null);
  const [drawerTag, setDrawerTag] = useState<TagRead | null>(null);
  const [impactCount, setImpactCount] = useState(1);
  const [impactLogging, setImpactLogging] = useState(false);
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
    setDrawerTag(null);
    setImpactCount(1);
    setTagImpacts([]);
    setTagImpactsError(null);
    setTagImpactsLoading(false);
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
    let cancelled = false;

    const loadImpacts = async () => {
      setTagImpactsLoading(true);
      setTagImpactsError(null);
      try {
        const data = await getTagImpacts(selectedDate);
        if (!cancelled) {
          setTagImpacts(data);
        }
      } catch (error) {
        if (!cancelled) {
          setTagImpactsError(getErrorMessage(error));
        }
      } finally {
        if (!cancelled) {
          setTagImpactsLoading(false);
        }
      }
    };

    loadImpacts();

    return () => {
      cancelled = true;
    };
  }, [selectedDate]);

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
  const categoryTabs = useMemo(() => buildTagCategoryTabs(tags), [tags]);
  const tagGridTags = useMemo(
    () =>
      pickerTags.filter(
        (tag) => normalizeTagCategory(tag.category) === selectedCategory,
      ),
    [pickerTags, selectedCategory],
  );
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

  useEffect(() => {
    if (!categoryTabs.includes(selectedCategory)) {
      setSelectedCategory(categoryTabs[0] ?? DEFAULT_TAG_CATEGORIES[0]);
    }
  }, [categoryTabs, selectedCategory]);

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
    async (tag: TagRead, count: number = 1) => {
      try {
        const event = await createTagEvent(selectedDate, { tag_id: tag.id, count });
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
        return true;
      } catch (error) {
        setActionError({
          message: getErrorMessage(error),
          retry: () => handleAddTagEvent(tag, count),
        });
        pushToast({ type: "error", message: "Failed to add tag event." });
        return false;
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
      if (newTagCategory === customCategoryValue && !customTagCategory.trim()) {
        pushToast({ type: "error", message: "Custom category is required." });
        return;
      }
      try {
        const resolvedCategory =
          newTagCategory === customCategoryValue
            ? normalizeTagCategory(customTagCategory)
            : normalizeTagCategory(newTagCategory);
        const created = await createTag({ name: trimmed, category: resolvedCategory });
        setTags((prev) => {
          const exists = prev.some((tag) => tag.id === created.id);
          if (exists) {
            return prev.map((tag) => (tag.id === created.id ? created : tag));
          }
          return [...prev, created];
        });
        setTagQuery("");
        await handleAddTagEvent(created, 1);
      } catch (error) {
        setActionError({
          message: getErrorMessage(error),
          retry: () => handleCreateTagAndAdd(name),
        });
        pushToast({ type: "error", message: "Failed to create tag." });
      }
    },
    [
      customTagCategory,
      handleAddTagEvent,
      newTagCategory,
      pushToast,
      setTagQuery,
      setTags,
    ],
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

  const handleOpenTagDrawer = useCallback((tag: TagRead) => {
    setDrawerTag(tag);
    setImpactCount(1);
  }, []);

  const handleCloseTagDrawer = useCallback(() => {
    setDrawerTag(null);
  }, []);

  const handleLogImpact = useCallback(async () => {
    if (!drawerTag || impactLogging) {
      return;
    }
    setImpactLogging(true);
    const success = await handleAddTagEvent(drawerTag, impactCount);
    if (success) {
      setDrawerTag(null);
      setImpactCount(1);
    }
    setImpactLogging(false);
  }, [drawerTag, handleAddTagEvent, impactCount, impactLogging]);

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

  const canOpenTag = Boolean(matchedTag) && !dayLoading;
  const canCreateTag = trimmedQuery.length > 0 && !matchedTag && !tagsLoading;
  const emptyCategoryLabel = showArchivedTags
    ? "No tags in this category yet."
    : "No active tags in this category yet.";
  const noteStatus = isSavingNote ? "Saving..." : lastSavedAt ? "Saved" : "Not saved yet";
  const lastSavedLabel = lastSavedAt ? formatTime(lastSavedAt) : null;

  const goals = day?.goals ?? [];
  const goalStatusById = useMemo(
    () => new Map(goals.map((goal) => [goal.goal_id, goal])),
    [goals],
  );
  const impactsByTagId = useMemo(
    () => new Map(tagImpacts.map((impact) => [impact.tag_id, impact])),
    [tagImpacts],
  );
  const selectedImpact = drawerTag ? impactsByTagId.get(drawerTag.id) : null;
  const selectedImpactGoals = selectedImpact?.goals ?? [];
  const impactGroups = useMemo(() => {
    const groups: Record<GoalStatus["target_window"], typeof selectedImpactGoals> =
      {
        day: [],
        week: [],
        month: [],
      };
    selectedImpactGoals.forEach((goal) => {
      groups[goal.target_window].push(goal);
    });
    Object.values(groups).forEach((items) =>
      items.sort((a, b) => a.goal_name.localeCompare(b.goal_name)),
    );
    return goalGroupOrder.map((targetWindow) => ({
      targetWindow,
      label: groupLabels[targetWindow],
      goals: groups[targetWindow],
    }));
  }, [selectedImpactGoals]);
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
          <h2>Tag board</h2>
          <div className="tag-board">
            <div className="tag-board__tabs" role="tablist" aria-label="Tag categories">
              {categoryTabs.map((category) => (
                <button
                  key={category}
                  className={`tag-tab${
                    selectedCategory === category ? " tag-tab--active" : ""
                  }`}
                  type="button"
                  role="tab"
                  aria-selected={selectedCategory === category}
                  onClick={() => setSelectedCategory(category)}
                >
                  {category}
                </button>
              ))}
            </div>
            <div className="tag-board__controls">
              <label className="option-card option-card--compact">
                <input
                  type="checkbox"
                  checked={showArchivedTags}
                  onChange={(event) => setShowArchivedTags(event.target.checked)}
                />
                <span>Show archived tags</span>
              </label>
              <button
                className="action-button action-button--ghost"
                type="button"
                onClick={() => setShowTagSearch((prev) => !prev)}
              >
                {showTagSearch ? "Hide search" : "Search & create"}
              </button>
            </div>

            {tagsLoading ? (
              <div className="status status--loading">Loading tags...</div>
            ) : tagGridTags.length === 0 ? (
              <div className="empty-state">{emptyCategoryLabel}</div>
            ) : (
              <div className="tag-board__grid">
                {tagGridTags.map((tag) => (
                  <button
                    key={tag.id}
                    className={`tag-tile${tag.active ? "" : " tag-tile--archived"}`}
                    type="button"
                    onClick={() => handleOpenTagDrawer(tag)}
                  >
                    <span className="tag-tile__name">{tag.name}</span>
                    {!tag.active && (
                      <span className="tag-badge tag-badge--archived">Archived</span>
                    )}
                  </button>
                ))}
              </div>
            )}

            {showTagSearch && (
              <div className="tag-search-panel">
                <div className="tag-search-panel__row">
                  <input
                    className="field"
                    type="text"
                    value={tagQuery}
                    onChange={(event) => setTagQuery(event.target.value)}
                    placeholder="Search or create a tag"
                  />
                  <button
                    className="action-button"
                    type="button"
                    onClick={() => {
                      if (matchedTag) {
                        handleOpenTagDrawer(matchedTag);
                        setTagQuery("");
                      }
                    }}
                    disabled={!canOpenTag}
                  >
                    Open tag
                  </button>
                  <button
                    className="action-button action-button--primary"
                    type="button"
                    onClick={() => handleCreateTagAndAdd(trimmedQuery)}
                    disabled={!canCreateTag}
                  >
                    Create tag & log
                  </button>
                </div>
                <div className="tag-search-panel__row">
                  <div className="tag-search-panel__field">
                    <label className="field-label" htmlFor="today-tag-category">
                      Category
                    </label>
                    <select
                      id="today-tag-category"
                      className="field"
                      value={newTagCategory}
                      onChange={(event) => setNewTagCategory(event.target.value)}
                    >
                      {DEFAULT_TAG_CATEGORIES.map((category) => (
                        <option key={category} value={category}>
                          {category}
                        </option>
                      ))}
                      <option value={customCategoryValue}>Custom…</option>
                    </select>
                  </div>
                  {newTagCategory === customCategoryValue && (
                    <div className="tag-search-panel__field">
                      <label
                        className="field-label"
                        htmlFor="today-tag-category-custom"
                      >
                        Custom category
                      </label>
                      <input
                        id="today-tag-category-custom"
                        className="field"
                        type="text"
                        value={customTagCategory}
                        onChange={(event) => setCustomTagCategory(event.target.value)}
                        placeholder="e.g. Recovery"
                      />
                    </div>
                  )}
                </div>
                {normalizedQuery && (
                  <>
                    {filteredTags.length === 0 ? (
                      <div className="empty-state">No tags match your search.</div>
                    ) : (
                      <div className="tag-search-results">
                        {filteredTags.map((tag) => (
                          <button
                            key={tag.id}
                            className="tag-search-result"
                            type="button"
                            onClick={() => {
                              handleOpenTagDrawer(tag);
                              setTagQuery("");
                            }}
                          >
                            <span>{tag.name}</span>
                            {!tag.active && (
                              <span className="tag-badge tag-badge--archived">
                                Archived
                              </span>
                            )}
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
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
                      {group.goals.map((goal: GoalStatus) => {
                        const ratingPending = Boolean(ratingPendingByGoal[goal.goal_id]);
                        const ratingDisabled = dayLoading || ratingPending;
                        return (
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
                                <div className="goal-rating" aria-busy={ratingPending}>
                                  <div className="goal-rating__input-row">
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
                                        handleRatingDraftChange(
                                          goal.goal_id,
                                          nextValue,
                                        );
                                      }}
                                      onBlur={() => {
                                        if (ratingDrafts[goal.goal_id] !== null) {
                                          return;
                                        }
                                        const savedValue = savedRatingsByGoal.get(
                                          goal.goal_id,
                                        );
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
                                      disabled={ratingDisabled}
                                    />
                                    {ratingPending && (
                                      <span className="goal-rating__status">
                                        Saving...
                                      </span>
                                    )}
                                  </div>
                                </div>
                              )}
                              <div
                                className={`goal-status goal-status--${goal.status}`}
                              >
                                {statusLabels[goal.status]}
                              </div>
                            </div>
                          </div>
                        );
                      })}
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
      {drawerTag && (
        <div className="impact-drawer impact-drawer--open">
          <button
            className="impact-drawer__backdrop"
            type="button"
            onClick={handleCloseTagDrawer}
            aria-label="Close impact drawer"
          />
          <div
            className="impact-drawer__panel"
            role="dialog"
            aria-modal="true"
            aria-label={`${drawerTag.name} impact`}
          >
            <div className="impact-drawer__header">
              <div>
                <div className="impact-drawer__label">Impact drawer</div>
                <div className="impact-drawer__title">{drawerTag.name}</div>
                <div className="impact-drawer__category">
                  Category: {normalizeTagCategory(drawerTag.category)}
                </div>
              </div>
              <button
                className="icon-button"
                type="button"
                onClick={handleCloseTagDrawer}
                aria-label="Close impact drawer"
              >
                &#10005;
              </button>
            </div>

            <div className="impact-drawer__count">
              <div className="impact-drawer__count-label">Log count</div>
              <div className="impact-count__quick">
                {impactCountOptions.map((count) => (
                  <button
                    key={count}
                    className={`toggle-chip${
                      impactCount === count ? " toggle-chip--active" : ""
                    }`}
                    type="button"
                    onClick={() => setImpactCount(count)}
                  >
                    +{count}
                  </button>
                ))}
              </div>
              <div className="impact-count__stepper">
                <button
                  className="impact-count__step"
                  type="button"
                  onClick={() =>
                    setImpactCount((prev) => Math.max(1, prev - 1))
                  }
                  aria-label="Decrease count"
                  disabled={impactCount <= 1}
                >
                  -
                </button>
                <span className="impact-count__value">{impactCount}</span>
                <button
                  className="impact-count__step"
                  type="button"
                  onClick={() => setImpactCount((prev) => prev + 1)}
                  aria-label="Increase count"
                >
                  +
                </button>
              </div>
              <div className="impact-drawer__actions">
                <button
                  className="action-button action-button--primary"
                  type="button"
                  onClick={handleLogImpact}
                  disabled={impactLogging || dayLoading}
                >
                  {impactLogging ? "Logging..." : `Log ${impactCount}`}
                </button>
              </div>
            </div>

            <div className="impact-drawer__impacts">
              <div className="impact-drawer__section-title">Impacted goals</div>
              {tagImpactsLoading ? (
                <div className="status status--loading">Loading impacts...</div>
              ) : tagImpactsError ? (
                <div className="status status--error" role="alert">
                  Couldn’t load impacts. {tagImpactsError}
                </div>
              ) : (
                <div className="impact-group-list">
                  {impactGroups.map((group) => (
                    <div key={group.targetWindow} className="impact-group">
                      <div className="impact-group__title">{group.label}</div>
                      {group.goals.length === 0 ? (
                        <div className="empty-state">No goals impacted.</div>
                      ) : (
                        <div className="impact-goal-list">
                          {group.goals.map((goal) => {
                            const status = goalStatusById.get(goal.goal_id);
                            const currentProgress = status?.progress ?? 0;
                            const nextProgress =
                              currentProgress + impactCount * goal.weight;
                            return (
                              <div key={goal.goal_id} className="impact-goal-row">
                                <div className="impact-goal__meta">
                                  <div className="impact-goal__name">
                                    {goal.goal_name}
                                  </div>
                                  <div className="impact-goal__details">
                                    <span className="impact-goal__weight">
                                      Weight {goal.weight}
                                    </span>
                                    {status && (
                                      <span
                                        className={`goal-status goal-status--${status.status}`}
                                      >
                                        {statusLabels[status.status]}
                                      </span>
                                    )}
                                  </div>
                                </div>
                                <div className="impact-goal__delta">
                                  <div className="impact-goal__progress">
                                    {currentProgress} → {nextProgress}
                                  </div>
                                  {status && (
                                    <div className="impact-goal__target">
                                      Target {status.target}
                                    </div>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
