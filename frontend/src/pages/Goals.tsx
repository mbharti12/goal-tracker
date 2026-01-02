import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { getErrorMessage } from "../api/client";
import {
  createGoal,
  createTag,
  deactivateTag,
  deleteGoal,
  reactivateTag,
  updateGoal,
} from "../api/endpoints";
import type { GoalRead, ScoringMode, TagRead, TargetWindow } from "../api/types";
import { useConditions } from "../hooks/useConditions";
import { useGoals } from "../hooks/useGoals";
import { useTags } from "../hooks/useTags";

type GoalFormState = {
  name: string;
  description: string;
  targetCount: string;
  targetWindow: TargetWindow;
  scoringMode: ScoringMode;
  active: boolean;
  tagIds: number[];
  conditionIds: number[];
};

type GoalFormErrors = {
  name?: string;
  targetCount?: string;
};

const scoringOptions: Array<{ value: ScoringMode; label: string }> = [
  { value: "count", label: "Counted progress" },
  { value: "binary", label: "Hit or miss" },
];

const windowOptions: Array<{ value: TargetWindow; label: string }> = [
  { value: "day", label: "Per day" },
  { value: "week", label: "Per week" },
];

const createEmptyForm = (): GoalFormState => ({
  name: "",
  description: "",
  targetCount: "1",
  targetWindow: "day",
  scoringMode: "count",
  active: true,
  tagIds: [],
  conditionIds: [],
});

const goalToForm = (goal: GoalRead): GoalFormState => ({
  name: goal.name,
  description: goal.description ?? "",
  targetCount: String(goal.target_count),
  targetWindow: goal.target_window,
  scoringMode: goal.scoring_mode,
  active: goal.active,
  tagIds: goal.tags.map((tag) => tag.tag.id),
  conditionIds: goal.conditions.map((condition) => condition.condition.id),
});

const formatTarget = (goal: GoalRead) =>
  `${goal.target_count} per ${goal.target_window}`;

const formatConditionLabel = (required: boolean, name: string) =>
  required ? name : `Not ${name}`;

export default function Goals() {
  const { goals, setGoals, loading: goalsLoading, error: goalsError, reload } =
    useGoals();
  const { tags, setTags, loading: tagsLoading, error: tagsError, reload: reloadTags } =
    useTags({ includeInactive: true });
  const {
    conditions,
    loading: conditionsLoading,
    error: conditionsError,
    reload: reloadConditions,
  } = useConditions();

  const [selectedGoalId, setSelectedGoalId] = useState<number | "new" | null>(null);
  const [formState, setFormState] = useState<GoalFormState>(() => createEmptyForm());
  const [formErrors, setFormErrors] = useState<GoalFormErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeactivating, setIsDeactivating] = useState(false);

  const [newTagName, setNewTagName] = useState("");
  const [tagError, setTagError] = useState<string | null>(null);
  const [isCreatingTag, setIsCreatingTag] = useState(false);
  const [showArchivedTags, setShowArchivedTags] = useState(false);
  const [showArchivedManager, setShowArchivedManager] = useState(false);
  const [tagManagementError, setTagManagementError] = useState<string | null>(null);
  const [tagActionId, setTagActionId] = useState<number | null>(null);

  const sortedGoals = useMemo(() => {
    return [...goals].sort((a, b) => {
      if (a.active !== b.active) {
        return a.active ? -1 : 1;
      }
      return a.name.localeCompare(b.name);
    });
  }, [goals]);

  const sortedTags = useMemo(
    () => [...tags].sort((a, b) => a.name.localeCompare(b.name)),
    [tags],
  );
  const activeTags = useMemo(
    () => sortedTags.filter((tag) => tag.active),
    [sortedTags],
  );
  const archivedTags = useMemo(
    () => sortedTags.filter((tag) => !tag.active),
    [sortedTags],
  );
  const tagOptions = useMemo(() => {
    if (showArchivedTags) {
      return sortedTags;
    }
    const selectedArchived = sortedTags.filter(
      (tag) => !tag.active && formState.tagIds.includes(tag.id),
    );
    const map = new Map<number, TagRead>();
    activeTags.forEach((tag) => map.set(tag.id, tag));
    selectedArchived.forEach((tag) => map.set(tag.id, tag));
    return Array.from(map.values());
  }, [activeTags, formState.tagIds, showArchivedTags, sortedTags]);
  const sortedConditions = useMemo(
    () => [...conditions].sort((a, b) => a.name.localeCompare(b.name)),
    [conditions],
  );

  const selectedGoal = useMemo(
    () =>
      selectedGoalId === null || selectedGoalId === "new"
        ? null
        : goals.find((goal) => goal.id === selectedGoalId) ?? null,
    [goals, selectedGoalId],
  );

  useEffect(() => {
    if (selectedGoalId !== null || goalsLoading) {
      return;
    }
    if (goalsError) {
      setSelectedGoalId("new");
      return;
    }
    if (goals.length > 0) {
      setSelectedGoalId(goals[0].id);
    } else {
      setSelectedGoalId("new");
    }
  }, [goals, goalsError, goalsLoading, selectedGoalId]);

  useEffect(() => {
    if (selectedGoalId === "new") {
      setFormState(createEmptyForm());
      setFormErrors({});
      setFormError(null);
      return;
    }
    if (selectedGoal) {
      setFormState(goalToForm(selectedGoal));
      setFormErrors({});
      setFormError(null);
    }
  }, [selectedGoal, selectedGoalId]);

  const updateForm = useCallback(
    (patch: Partial<GoalFormState>) => {
      setFormState((prev) => ({ ...prev, ...patch }));
    },
    [setFormState],
  );

  const toggleId = useCallback(
    (ids: number[], id: number) =>
      ids.includes(id) ? ids.filter((value) => value !== id) : [...ids, id],
    [],
  );

  const handleSelectGoal = useCallback((goalId: number) => {
    setSelectedGoalId(goalId);
  }, []);

  const handleNewGoal = useCallback(() => {
    setSelectedGoalId("new");
  }, []);

  const validateForm = useCallback((state: GoalFormState) => {
    const errors: GoalFormErrors = {};
    const trimmedName = state.name.trim();
    if (!trimmedName) {
      errors.name = "Name is required.";
    }
    const countValue = Number(state.targetCount);
    if (!Number.isFinite(countValue) || !Number.isInteger(countValue) || countValue <= 0) {
      errors.targetCount = "Target must be a whole number greater than zero.";
    }
    return { errors, countValue };
  }, []);

  const buildPayload = useCallback(
    (state: GoalFormState, targetCount: number) => ({
      name: state.name.trim(),
      description: state.description.trim() ? state.description.trim() : null,
      active: state.active,
      target_window: state.targetWindow,
      target_count: targetCount,
      scoring_mode: state.scoringMode,
      tags: state.tagIds.map((id) => ({ tag_id: id })),
      conditions: state.conditionIds.map((id) => ({
        condition_id: id,
        required_value: true,
      })),
    }),
    [],
  );

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setFormError(null);

      const { errors, countValue } = validateForm(formState);
      setFormErrors(errors);
      if (Object.keys(errors).length > 0) {
        return;
      }

      setIsSaving(true);
      try {
        const payload = buildPayload(formState, countValue);
        if (selectedGoalId === "new" || selectedGoalId === null) {
          const created = await createGoal(payload);
          setGoals((prev) => [created, ...prev.filter((goal) => goal.id !== created.id)]);
          setSelectedGoalId(created.id);
          setFormState(goalToForm(created));
        } else {
          const updated = await updateGoal(selectedGoalId, payload);
          setGoals((prev) =>
            prev.map((goal) => (goal.id === updated.id ? updated : goal)),
          );
          setFormState(goalToForm(updated));
        }
      } catch (error) {
        setFormError(getErrorMessage(error));
      } finally {
        setIsSaving(false);
      }
    },
    [buildPayload, formState, selectedGoalId, setGoals, validateForm],
  );

  const handleDeactivate = useCallback(async () => {
    if (!selectedGoal || isDeactivating) {
      return;
    }
    const confirmed = window.confirm(
      `Deactivate "${selectedGoal.name}"? You can reactivate it later.`,
    );
    if (!confirmed) {
      return;
    }
    setIsDeactivating(true);
    try {
      const updated = await deleteGoal(selectedGoal.id);
      setGoals((prev) =>
        prev.map((goal) => (goal.id === updated.id ? updated : goal)),
      );
      setFormState(goalToForm(updated));
    } catch (error) {
      setFormError(getErrorMessage(error));
    } finally {
      setIsDeactivating(false);
    }
  }, [isDeactivating, selectedGoal, setGoals]);

  const handleCreateTag = useCallback(async () => {
    const trimmed = newTagName.trim();
    if (!trimmed || isCreatingTag) {
      return;
    }
    const existing = tags.find(
      (tag) => tag.name.toLowerCase() === trimmed.toLowerCase(),
    );
    if (existing && existing.active) {
      setTagError("That tag already exists.");
      updateForm({
        tagIds: formState.tagIds.includes(existing.id)
          ? formState.tagIds
          : [...formState.tagIds, existing.id],
      });
      setNewTagName("");
      return;
    }
    setIsCreatingTag(true);
    setTagError(null);
    try {
      const created = await createTag({ name: trimmed });
      setTags((prev) => {
        const exists = prev.some((tag) => tag.id === created.id);
        if (exists) {
          return prev.map((tag) => (tag.id === created.id ? created : tag));
        }
        return [...prev, created];
      });
      updateForm({
        tagIds: formState.tagIds.includes(created.id)
          ? formState.tagIds
          : [...formState.tagIds, created.id],
      });
      setNewTagName("");
    } catch (error) {
      setTagError(getErrorMessage(error));
    } finally {
      setIsCreatingTag(false);
    }
  }, [formState.tagIds, isCreatingTag, newTagName, tags, setTags, updateForm]);

  const handleArchiveTag = useCallback(
    async (tagId: number) => {
      const tag = tags.find((entry) => entry.id === tagId);
      if (!tag || tagActionId === tagId) {
        return;
      }
      const confirmed = window.confirm(
        "Archive tag? Past entries will remain; tag will be hidden from quick-add.",
      );
      if (!confirmed) {
        return;
      }
      setTagActionId(tagId);
      setTagManagementError(null);
      try {
        const updated = await deactivateTag(tagId);
        setTags((prev) =>
          prev.map((entry) => (entry.id === updated.id ? updated : entry)),
        );
        await reloadTags();
      } catch (error) {
        setTagManagementError(getErrorMessage(error));
      } finally {
        setTagActionId(null);
      }
    },
    [reloadTags, setTags, tagActionId, tags],
  );

  const handleUnarchiveTag = useCallback(
    async (tagId: number) => {
      if (tagActionId === tagId) {
        return;
      }
      setTagActionId(tagId);
      setTagManagementError(null);
      try {
        const updated = await reactivateTag(tagId);
        setTags((prev) =>
          prev.map((entry) => (entry.id === updated.id ? updated : entry)),
        );
        await reloadTags();
      } catch (error) {
        setTagManagementError(getErrorMessage(error));
      } finally {
        setTagActionId(null);
      }
    },
    [reloadTags, setTags, tagActionId],
  );

  const loadGoalError = goalsError;
  const loadMetaError = tagsError ?? conditionsError;
  const metaLoading = tagsLoading || conditionsLoading;
  const isCreating = selectedGoalId === "new" || selectedGoalId === null;
  const emptyTagsMessage = showArchivedTags ? "No tags yet." : "No active tags yet.";

  return (
    <section className="page">
      <div className="goals-layout">
        <div className="card">
          <div className="goals-list__header">
            <div>
              <h2>Goals</h2>
              <p>Design the goals you want to keep in focus.</p>
            </div>
            <button className="action-button" type="button" onClick={handleNewGoal}>
              New goal
            </button>
          </div>

          {loadGoalError && (
            <div className="status status--error" role="alert">
              <div>Couldn’t load goals. {loadGoalError}</div>
              <button className="action-button" type="button" onClick={reload}>
                Retry
              </button>
            </div>
          )}

          {goalsLoading && !loadGoalError && (
            <div className="status status--loading">Loading goals…</div>
          )}

          {!goalsLoading && !loadGoalError && sortedGoals.length === 0 && (
            <div className="status status--loading">
              No goals yet. Create the first one on the right.
            </div>
          )}

          <div className="goal-list">
            {sortedGoals.map((goal) => {
              const isSelected = goal.id === selectedGoalId;
              const tagsLabel =
                goal.tags.length > 0
                  ? goal.tags.map((tag) => tag.tag.name)
                  : ["No tags yet"];
              const conditionsLabel =
                goal.conditions.length > 0
                  ? goal.conditions.map((condition) =>
                      formatConditionLabel(
                        condition.required_value,
                        condition.condition.name,
                      ),
                    )
                  : ["Always applicable"];

              return (
                <button
                  key={goal.id}
                  type="button"
                  className={`goal-tile${isSelected ? " goal-tile--active" : ""}`}
                  onClick={() => handleSelectGoal(goal.id)}
                >
                  <div className="goal-tile__header">
                    <div className="goal-tile__name">{goal.name}</div>
                    <div className="goal-tile__target">{formatTarget(goal)}</div>
                  </div>
                  <div className="goal-tile__meta">
                    <span
                      className={`goal-badge${
                        goal.active ? "" : " goal-badge--inactive"
                      }`}
                    >
                      {goal.active ? "Active" : "Inactive"}
                    </span>
                    <span>Scoring: {goal.scoring_mode}</span>
                    {goal.description && <span>{goal.description}</span>}
                  </div>
                  <div className="goal-tile__chips">
                    {tagsLabel.map((label) => (
                      <span
                        key={`${goal.id}-tag-${label}`}
                        className={`goal-pill${
                          label === "No tags yet" ? " goal-pill--empty" : ""
                        }`}
                      >
                        {label}
                      </span>
                    ))}
                  </div>
                  <div className="goal-tile__chips">
                    {conditionsLabel.map((label) => (
                      <span
                        key={`${goal.id}-condition-${label}`}
                        className={`goal-pill goal-pill--condition${
                          label === "Always applicable" ? " goal-pill--empty" : ""
                        }`}
                      >
                        {label}
                      </span>
                    ))}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="card">
          <form className="goals-form" onSubmit={handleSubmit}>
            <div className="goals-form__header">
              <div>
                <h2>{isCreating ? "Create goal" : "Edit goal"}</h2>
                <p>
                  {isCreating
                    ? "Define the outcomes and when they apply."
                    : "Tune the details, tags, or conditions."}
                </p>
              </div>
              {!isCreating && selectedGoal && (
                <button
                  className="action-button action-button--ghost"
                  type="button"
                  onClick={handleDeactivate}
                  disabled={isDeactivating}
                >
                  {isDeactivating ? "Deactivating…" : "Deactivate"}
                </button>
              )}
            </div>

            {formError && (
              <div className="status status--error" role="alert">
                {formError}
              </div>
            )}

            <div className="field-group">
              <label className="field-label" htmlFor="goal-name">
                Name *
              </label>
              <input
                id="goal-name"
                className="field"
                type="text"
                value={formState.name}
                onChange={(event) => {
                  updateForm({ name: event.target.value });
                  setFormErrors((prev) => ({ ...prev, name: undefined }));
                }}
                placeholder="e.g. Consistent workout"
              />
              {formErrors.name && <div className="field-error">{formErrors.name}</div>}
            </div>

            <div className="field-group">
              <label className="field-label" htmlFor="goal-description">
                Description
              </label>
              <textarea
                id="goal-description"
                className="field"
                rows={3}
                value={formState.description}
                onChange={(event) => updateForm({ description: event.target.value })}
                placeholder="Optional context or definition."
              />
            </div>

            <div className="field-row">
              <div className="field-group">
                <label className="field-label" htmlFor="goal-target-count">
                  Target count
                </label>
                <input
                  id="goal-target-count"
                  className="field"
                  type="number"
                  min={1}
                  step={1}
                  value={formState.targetCount}
                  onChange={(event) => {
                    updateForm({ targetCount: event.target.value });
                    setFormErrors((prev) => ({ ...prev, targetCount: undefined }));
                  }}
                />
                {formErrors.targetCount && (
                  <div className="field-error">{formErrors.targetCount}</div>
                )}
              </div>

              <div className="field-group">
                <label className="field-label" htmlFor="goal-target-window">
                  Window
                </label>
                <select
                  id="goal-target-window"
                  className="field"
                  value={formState.targetWindow}
                  onChange={(event) =>
                    updateForm({ targetWindow: event.target.value as TargetWindow })
                  }
                >
                  {windowOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="field-group">
                <label className="field-label" htmlFor="goal-scoring">
                  Scoring mode
                </label>
                <select
                  id="goal-scoring"
                  className="field"
                  value={formState.scoringMode}
                  onChange={(event) =>
                    updateForm({ scoringMode: event.target.value as ScoringMode })
                  }
                >
                  {scoringOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="field-group">
              <label className="field-label">Active</label>
              <label className="option-card">
                <input
                  type="checkbox"
                  checked={formState.active}
                  onChange={(event) => updateForm({ active: event.target.checked })}
                />
                <span>Goal is active</span>
              </label>
            </div>

            <div className="field-group">
              <label className="field-label">Tags</label>
              <div className="inline-row">
                <input
                  className="field field--compact"
                  type="text"
                  value={newTagName}
                  onChange={(event) => {
                    setNewTagName(event.target.value);
                    setTagError(null);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      handleCreateTag();
                    }
                  }}
                  placeholder="Create a new tag"
                />
                <button
                  className="action-button"
                  type="button"
                  onClick={handleCreateTag}
                  disabled={isCreatingTag || !newTagName.trim()}
                >
                  {isCreatingTag ? "Adding…" : "Add tag"}
                </button>
              </div>
              <div className="inline-row">
                <label className="option-card option-card--compact">
                  <input
                    type="checkbox"
                    checked={showArchivedTags}
                    onChange={(event) => setShowArchivedTags(event.target.checked)}
                  />
                  <span>Show archived tags</span>
                </label>
              </div>
              {tagError && <div className="field-error">{tagError}</div>}
              {tagsLoading ? (
                <div className="status status--loading">Loading tags…</div>
              ) : tagsError ? (
                <div className="status status--error" role="alert">
                  <div>Couldn’t load tags. {tagsError}</div>
                  <button className="action-button" type="button" onClick={reloadTags}>
                    Retry
                  </button>
                </div>
              ) : tagOptions.length === 0 ? (
                <div className="status status--loading">{emptyTagsMessage}</div>
              ) : (
                <div className="chip-row">
                  {tagOptions.map((tag) => {
                    const isActive = formState.tagIds.includes(tag.id);
                    return (
                      <button
                        key={tag.id}
                        type="button"
                        className={`toggle-chip${
                          isActive ? " toggle-chip--active" : ""
                        }`}
                        onClick={() =>
                          updateForm({
                            tagIds: toggleId(formState.tagIds, tag.id),
                          })
                        }
                        aria-pressed={isActive}
                      >
                        {tag.name}
                        {!tag.active && " (archived)"}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="field-group">
              <label className="field-label">Conditions</label>
              <div className="field-hint">
                Goal applies only when all selected conditions are true.
              </div>
              {conditionsLoading ? (
                <div className="status status--loading">Loading conditions…</div>
              ) : conditionsError ? (
                <div className="status status--error" role="alert">
                  <div>Couldn’t load conditions. {conditionsError}</div>
                  <button
                    className="action-button"
                    type="button"
                    onClick={reloadConditions}
                  >
                    Retry
                  </button>
                </div>
              ) : sortedConditions.length === 0 ? (
                <div className="status status--loading">
                  No conditions yet. The goal will always apply.
                </div>
              ) : (
                <div className="chip-row">
                  {sortedConditions.map((condition) => {
                    const isActive = formState.conditionIds.includes(condition.id);
                    return (
                      <button
                        key={condition.id}
                        type="button"
                        className={`toggle-chip${
                          isActive ? " toggle-chip--active" : ""
                        }`}
                        onClick={() =>
                          updateForm({
                            conditionIds: toggleId(formState.conditionIds, condition.id),
                          })
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

            <div className="goals-actions">
              <button
                className="action-button action-button--primary"
                type="submit"
                disabled={isSaving}
              >
                {isSaving ? "Saving…" : "Save goal"}
              </button>
              {metaLoading && (
                <span className="field-hint">Waiting for tags/conditions…</span>
              )}
            </div>

            {loadMetaError && (
              <div className="status status--error" role="alert">
                Some metadata failed to load. Tag and condition selections may be
                incomplete.
              </div>
            )}
          </form>
        </div>

        <div className="card tag-management">
          <div className="tag-management__header">
            <div>
              <h2>Tag management</h2>
              <p>Archive tags to hide them from quick-add while keeping history.</p>
            </div>
            <label className="option-card option-card--compact">
              <input
                type="checkbox"
                checked={showArchivedManager}
                onChange={(event) => setShowArchivedManager(event.target.checked)}
              />
              <span>Show archived</span>
            </label>
          </div>

          {tagsLoading ? (
            <div className="status status--loading">Loading tags…</div>
          ) : tagsError ? (
            <div className="status status--error" role="alert">
              <div>Couldn’t load tags. {tagsError}</div>
              <button className="action-button" type="button" onClick={reloadTags}>
                Retry
              </button>
            </div>
          ) : (
            <>
              <div className="tag-management__section">
                <div className="tag-management__section-title">Active tags</div>
                {activeTags.length === 0 ? (
                  <div className="empty-state">No active tags right now.</div>
                ) : (
                  <div className="tag-management__list">
                    {activeTags.map((tag) => (
                      <div key={tag.id} className="tag-management__row">
                        <span>{tag.name}</span>
                        <button
                          className="action-button action-button--ghost"
                          type="button"
                          onClick={() => handleArchiveTag(tag.id)}
                          disabled={tagActionId === tag.id}
                        >
                          {tagActionId === tag.id ? "Archiving…" : "Archive"}
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {showArchivedManager && (
                <div className="tag-management__section">
                  <div className="tag-management__section-title">
                    Archived tags
                  </div>
                  {archivedTags.length === 0 ? (
                    <div className="empty-state">No archived tags.</div>
                  ) : (
                    <div className="tag-management__list">
                      {archivedTags.map((tag) => (
                        <div key={tag.id} className="tag-management__row">
                          <span>{tag.name}</span>
                          <button
                            className="action-button action-button--ghost"
                            type="button"
                            onClick={() => handleUnarchiveTag(tag.id)}
                            disabled={tagActionId === tag.id}
                          >
                            {tagActionId === tag.id ? "Restoring…" : "Unarchive"}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {tagManagementError && (
            <div className="status status--error" role="alert">
              {tagManagementError}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
