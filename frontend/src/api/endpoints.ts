import { apiRequest } from "./client";
import { request } from "./generated/client";
import type {
  CalendarDayRead,
  CalendarSummaryRead,
  ConditionCreate,
  ConditionRead,
  DayConditionRead,
  DayConditionsUpdate,
  DayEntryRead,
  DayGoalRatingRead,
  DayGoalRatingsUpdate,
  DayNoteUpdate,
  DayRead,
  GoalTrendResponse,
  GoalCreate,
  GoalRead,
  GoalUpdate,
  HealthResponse,
  LlmHealthResponse,
  ReviewFilterRequest,
  ReviewFilterResponse,
  ReviewQueryRequest,
  ReviewQueryResponse,
  TagImpactRead,
  TagCreate,
  TagEventCreate,
  TagEventDeleteResponse,
  TagEventRead,
  TagRead,
  TrendBucket,
  TrendCompareRequest,
  TrendCompareResponse,
} from "./types";

export const getHealth = () => apiRequest<HealthResponse>("/health");
export const getLlmHealth = () => apiRequest<LlmHealthResponse>("/llm/health");

export const listGoals = () => apiRequest<GoalRead[]>("/goals");

export const createGoal = (payload: GoalCreate) =>
  apiRequest<GoalRead>("/goals", { method: "POST", body: payload });

export const updateGoal = (goalId: number, payload: GoalUpdate) =>
  apiRequest<GoalRead>(`/goals/${goalId}`, { method: "PUT", body: payload });

export const deleteGoal = (goalId: number) =>
  apiRequest<GoalRead>(`/goals/${goalId}`, { method: "DELETE" });

export const listTags = (options?: { includeInactive?: boolean }) => {
  const params = new URLSearchParams();
  if (options?.includeInactive) {
    params.set("include_inactive", "true");
  }
  const suffix = params.toString();
  return apiRequest<TagRead[]>(suffix ? `/tags?${suffix}` : "/tags");
};

export const createTag = (payload: TagCreate) =>
  apiRequest<TagRead>("/tags", { method: "POST", body: payload });

export const deactivateTag = (tagId: number) =>
  apiRequest<TagRead>(`/tags/${tagId}/deactivate`, { method: "PUT" });

export const reactivateTag = (tagId: number) =>
  apiRequest<TagRead>(`/tags/${tagId}/reactivate`, { method: "PUT" });

export const deleteTagHard = (tagId: number) =>
  apiRequest<TagRead>(`/tags/${tagId}`, { method: "DELETE" });

export const listConditions = (options?: { includeInactive?: boolean }) => {
  const params = new URLSearchParams();
  if (options?.includeInactive) {
    params.set("include_inactive", "true");
  }
  const suffix = params.toString();
  return apiRequest<ConditionRead[]>(suffix ? `/conditions?${suffix}` : "/conditions");
};

export const createCondition = (payload: ConditionCreate) =>
  apiRequest<ConditionRead>("/conditions", { method: "POST", body: payload });

export const deactivateCondition = (conditionId: number) =>
  apiRequest<ConditionRead>(`/conditions/${conditionId}/deactivate`, {
    method: "PUT",
  });

export const reactivateCondition = (conditionId: number) =>
  apiRequest<ConditionRead>(`/conditions/${conditionId}/reactivate`, {
    method: "PUT",
  });

export const getDay = (date: string) => apiRequest<DayRead>(`/days/${date}`);

export const getTagImpacts = (date: string) =>
  apiRequest<TagImpactRead[]>(`/days/${date}/tag-impacts`);

export const getCalendar = (start: string, end: string) => {
  const params = new URLSearchParams({ start, end });
  return apiRequest<CalendarDayRead[]>(`/calendar?${params.toString()}`);
};

export const getCalendarSummary = (start: string, end: string) => {
  const params = new URLSearchParams({ start, end });
  return apiRequest<CalendarSummaryRead>(`/calendar/summary?${params.toString()}`);
};

export const upsertDayNote = (date: string, payload: DayNoteUpdate) =>
  apiRequest<DayEntryRead>(`/days/${date}/note`, { method: "PUT", body: payload });

export const upsertDayConditions = (date: string, payload: DayConditionsUpdate) =>
  apiRequest<DayConditionRead[]>(`/days/${date}/conditions`, {
    method: "PUT",
    body: payload,
  });

export const upsertDayRatings = (date: string, payload: DayGoalRatingsUpdate) =>
  apiRequest<DayGoalRatingRead[]>(`/days/${date}/ratings`, {
    method: "PUT",
    body: payload,
  });

export const createTagEvent = (date: string, payload: TagEventCreate) =>
  apiRequest<TagEventRead>(`/days/${date}/tag-events`, {
    method: "POST",
    body: payload,
  });

export const deleteTagEvent = (eventId: number) =>
  apiRequest<TagEventDeleteResponse>(`/tag-events/${eventId}`, {
    method: "DELETE",
  });

export const reviewQuery = (payload: ReviewQueryRequest) =>
  apiRequest<ReviewQueryResponse>("/review/query", {
    method: "POST",
    body: payload,
  });

export const reviewFilter = (payload: ReviewFilterRequest) =>
  apiRequest<ReviewFilterResponse>("/review/filter", {
    method: "POST",
    body: payload,
  });

export const listNotifications = () => request("/notifications", "get");

export const markNotificationRead = (notificationId: number) =>
  request(
    `/notifications/${notificationId}/read` as "/notifications/{notification_id}/read",
    "post",
  );

export const getGoalTrend = (
  goalId: number,
  start: string,
  end: string,
  bucket: TrendBucket,
) => {
  const params = new URLSearchParams({ start, end, bucket });
  return apiRequest<GoalTrendResponse>(`/goals/${goalId}/trend?${params.toString()}`);
};

export const compareTrends = (
  goalIds: number[],
  start: string,
  end: string,
  bucket: TrendBucket,
) =>
  apiRequest<TrendCompareResponse>("/trends/compare", {
    method: "POST",
    body: { goal_ids: goalIds, start, end, bucket } satisfies TrendCompareRequest,
  });
