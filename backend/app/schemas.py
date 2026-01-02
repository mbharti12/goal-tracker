from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import ScoringMode, TargetWindow


class TagBase(BaseModel):
    name: str


class TagCreate(TagBase):
    pass


class TagRead(TagBase):
    id: int
    active: bool

    model_config = ConfigDict(from_attributes=True)


class ConditionBase(BaseModel):
    name: str


class ConditionCreate(ConditionBase):
    pass


class ConditionRead(ConditionBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class GoalTagInput(BaseModel):
    tag_id: int
    weight: int = Field(default=1, ge=1)


class GoalConditionInput(BaseModel):
    condition_id: int
    required_value: bool = True


class GoalTagRead(BaseModel):
    tag: TagRead
    weight: int

    model_config = ConfigDict(from_attributes=True)


class GoalConditionRead(BaseModel):
    condition: ConditionRead
    required_value: bool

    model_config = ConfigDict(from_attributes=True)


class GoalBase(BaseModel):
    name: str
    description: Optional[str] = None
    active: bool = True
    target_window: TargetWindow
    target_count: int
    scoring_mode: ScoringMode


class GoalCreate(GoalBase):
    tags: List[GoalTagInput] = Field(default_factory=list)
    conditions: List[GoalConditionInput] = Field(default_factory=list)


class GoalUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    target_window: Optional[TargetWindow] = None
    target_count: Optional[int] = None
    scoring_mode: Optional[ScoringMode] = None
    tags: Optional[List[GoalTagInput]] = None
    conditions: Optional[List[GoalConditionInput]] = None


class GoalRead(GoalBase):
    id: int
    tags: List[GoalTagRead] = Field(default_factory=list)
    conditions: List[GoalConditionRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class DayEntryRead(BaseModel):
    date: str
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DayNoteUpdate(BaseModel):
    note: str


class DayConditionInput(BaseModel):
    condition_id: int
    value: bool


class DayConditionsUpdate(BaseModel):
    conditions: List[DayConditionInput] = Field(default_factory=list)


class DayConditionRead(BaseModel):
    condition_id: int
    name: str
    value: bool


class TagEventCreate(BaseModel):
    tag_id: Optional[int] = None
    tag_name: Optional[str] = None
    count: int = Field(default=1, ge=1)
    ts: Optional[datetime] = None
    note: Optional[str] = None

    @model_validator(mode="after")
    def _require_tag_reference(self):
        if self.tag_id is None and not self.tag_name:
            raise ValueError("tag_id or tag_name is required")
        return self


class TagEventRead(BaseModel):
    id: int
    date: str
    tag_id: int
    tag_name: str
    ts: Optional[datetime] = None
    count: int
    note: Optional[str] = None


class TagEventDeleteResponse(BaseModel):
    deleted: bool


class DayRead(BaseModel):
    day_entry: Optional[DayEntryRead] = None
    conditions: List[DayConditionRead] = Field(default_factory=list)
    tag_events: List[TagEventRead] = Field(default_factory=list)
    goals: List[dict] = Field(default_factory=list)


class CalendarConditionRead(BaseModel):
    condition_id: int
    name: str
    value: bool


class CalendarTagRead(BaseModel):
    tag_id: int
    name: str
    count: int


class CalendarDayRead(BaseModel):
    date: str
    applicable_goals: int
    met_goals: int
    completion_ratio: float
    conditions: List[CalendarConditionRead] = Field(default_factory=list)
    tags: List[CalendarTagRead] = Field(default_factory=list)


class QueryPlan(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    last_n_days: Optional[int] = Field(default=None, ge=1)
    days_of_week: Optional[List[str]] = None
    conditions_any: Optional[List[str]] = None
    conditions_all: Optional[List[str]] = None
    goals: Optional[List[str]] = None
    intent: Literal["summary", "patterns", "coach", "report"]

    model_config = ConfigDict(extra="forbid")

    @field_validator("start_date", "end_date")
    def _validate_date(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("Invalid date format. Expected YYYY-MM-DD.") from exc
        return value

    @field_validator("days_of_week")
    def _validate_days_of_week(
        cls, value: Optional[List[str]]
    ) -> Optional[List[str]]:
        if value is None:
            return value
        allowed = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        invalid = [item for item in value if item not in allowed]
        if invalid:
            invalid_values = ", ".join(invalid)
            raise ValueError(f"Invalid days_of_week: {invalid_values}")
        return value

    @field_validator(
        "days_of_week", "conditions_any", "conditions_all", "goals", mode="before"
    )
    def _normalize_empty_lists(cls, value):
        if value == []:
            return None
        return value


class ReviewQueryRequest(BaseModel):
    prompt: str = Field(min_length=1)


class ReviewFilterRequest(BaseModel):
    start_date: str
    end_date: str
    days_of_week: Optional[List[str]] = None
    conditions_all: Optional[List[str]] = None
    conditions_any: Optional[List[str]] = None
    goals: Optional[List[str]] = None

    @field_validator("start_date", "end_date")
    def _validate_review_date(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("Invalid date format. Expected YYYY-MM-DD.") from exc
        return value

    @field_validator("days_of_week")
    def _validate_review_days_of_week(
        cls, value: Optional[List[str]]
    ) -> Optional[List[str]]:
        if value is None:
            return value
        allowed = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        invalid = [item for item in value if item not in allowed]
        if invalid:
            invalid_values = ", ".join(invalid)
            raise ValueError(f"Invalid days_of_week: {invalid_values}")
        return value

    @field_validator(
        "days_of_week", "conditions_all", "conditions_any", "goals", mode="before"
    )
    def _normalize_review_empty_lists(cls, value):
        if value == []:
            return None
        return value


class ReviewDateRange(BaseModel):
    start: str
    end: str


class ReviewFilters(BaseModel):
    dow: Optional[List[str]] = None
    conditions_all: Optional[List[str]] = None
    conditions_any: Optional[List[str]] = None
    goals: Optional[List[str]] = None


class ReviewDaySummary(BaseModel):
    applicable_goals: int
    met_goals: int
    completion_ratio: float


class ReviewDay(BaseModel):
    date: str
    note: Optional[str] = None
    summary: ReviewDaySummary
    goals: List[dict] = Field(default_factory=list)


class ReviewContext(BaseModel):
    date_range: ReviewDateRange
    filters: ReviewFilters
    days: List[ReviewDay] = Field(default_factory=list)
    truncated: bool = False


class ReviewFilterResponse(BaseModel):
    context: ReviewContext


class ReviewDebugFilters(BaseModel):
    dow: Optional[List[str]] = None
    conditions: Optional[List[str]] = None
    goals: Optional[List[str]] = None


class ReviewDebug(BaseModel):
    plan: QueryPlan
    date_range: ReviewDateRange
    filters: ReviewDebugFilters
    days_included: int
    truncated: bool


class ReviewQueryResponse(BaseModel):
    answer: str
    debug: ReviewDebug
