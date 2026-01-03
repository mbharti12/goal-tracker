import type { components } from "./generated/schema";

export type ApiErrorResponse = {
  detail?: string;
};

export type HealthResponse = {
  status: string;
};

export type LlmHealthResponse = {
  reachable: boolean;
  model: string;
  base_url: string;
  error?: string | null;
};

type Schemas = components["schemas"];

export type TagCreate = Schemas["TagCreate"];
export type TagRead = Schemas["TagRead"];
export type ConditionCreate = Schemas["ConditionCreate"];
export type ConditionRead = Schemas["ConditionRead"];
export type TargetWindow = Schemas["TargetWindow"];
export type ScoringMode = Schemas["ScoringMode"];
export type GoalTagInput = Schemas["GoalTagInput"];
export type GoalConditionInput = Schemas["GoalConditionInput"];
export type GoalTagRead = Schemas["GoalTagRead"];
export type GoalConditionRead = Schemas["GoalConditionRead"];
export type GoalBase = Schemas["GoalBase"];
export type GoalCreate = Schemas["GoalCreate"];
export type GoalUpdate = Schemas["GoalUpdate"];
export type GoalRead = Schemas["GoalRead"];
export type DayEntryRead = Schemas["DayEntryRead"];
export type DayNoteUpdate = Schemas["DayNoteUpdate"];
export type DayConditionInput = Schemas["DayConditionInput"];
export type DayConditionsUpdate = Schemas["DayConditionsUpdate"];
export type DayConditionRead = Schemas["DayConditionRead"];
export type TagEventCreate = Schemas["TagEventCreate"];
export type TagEventRead = Schemas["TagEventRead"];
export type TagEventDeleteResponse = Schemas["TagEventDeleteResponse"];
export type CalendarConditionRead = Schemas["CalendarConditionRead"];
export type CalendarTagRead = Schemas["CalendarTagRead"];
export type CalendarDayRead = Schemas["CalendarDayRead"];
export type CalendarWeekRead = Schemas["CalendarWeekRead"];
export type CalendarMonthRead = Schemas["CalendarMonthRead"];
export type CalendarSummaryRead = Schemas["CalendarSummaryRead"];
export type QueryPlan = Schemas["QueryPlan"];
export type ReviewQueryRequest = Schemas["ReviewQueryRequest"];
export type ReviewFilterRequest = Schemas["ReviewFilterRequest"];
export type ReviewDateRange = Schemas["ReviewDateRange"];
export type ReviewFilters = Schemas["ReviewFilters"];
export type ReviewDaySummary = Schemas["ReviewDaySummary"];
export type ReviewDebugFilters = Schemas["ReviewDebugFilters"];
export type ReviewDebug = Schemas["ReviewDebug"];
export type ReviewQueryResponse = Schemas["ReviewQueryResponse"];

export type GoalStatus = {
  goal_id: number;
  goal_name: string;
  applicable: boolean;
  status: "met" | "partial" | "missed" | "na";
  progress: number;
  target: number;
  target_window: TargetWindow;
};

export type DayRead = Omit<Schemas["DayRead"], "goals"> & {
  goals: GoalStatus[];
};

export type ReviewDay = Omit<Schemas["ReviewDay"], "goals"> & {
  goals: GoalStatus[];
};

export type ReviewContext = Omit<Schemas["ReviewContext"], "days"> & {
  days: ReviewDay[];
};

export type ReviewFilterResponse = Omit<Schemas["ReviewFilterResponse"], "context"> & {
  context: ReviewContext;
};
