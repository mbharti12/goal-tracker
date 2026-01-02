from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class TargetWindow(str, Enum):
    day = "day"
    week = "week"


class ScoringMode(str, Enum):
    count = "count"
    binary = "binary"


class Goal(SQLModel, table=True):
    __tablename__ = "goals"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = None
    active: bool = Field(default=True)
    target_window: TargetWindow
    target_count: int
    scoring_mode: ScoringMode

    goal_tags: List["GoalTag"] = Relationship(back_populates="goal")
    goal_conditions: List["GoalCondition"] = Relationship(back_populates="goal")

    @property
    def tags(self) -> List["GoalTag"]:
        return self.goal_tags

    @property
    def conditions(self) -> List["GoalCondition"]:
        return self.goal_conditions


class Tag(SQLModel, table=True):
    __tablename__ = "tags"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    active: bool = Field(default=True, index=True)

    goal_tags: List["GoalTag"] = Relationship(back_populates="tag")
    tag_events: List["TagEvent"] = Relationship(back_populates="tag")


class GoalTag(SQLModel, table=True):
    __tablename__ = "goal_tags"

    goal_id: int = Field(foreign_key="goals.id", primary_key=True)
    tag_id: int = Field(foreign_key="tags.id", primary_key=True)
    weight: int = Field(default=1)

    goal: Optional[Goal] = Relationship(back_populates="goal_tags")
    tag: Optional[Tag] = Relationship(back_populates="goal_tags")


class Condition(SQLModel, table=True):
    __tablename__ = "conditions"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)

    goal_conditions: List["GoalCondition"] = Relationship(back_populates="condition")


class GoalCondition(SQLModel, table=True):
    __tablename__ = "goal_conditions"

    goal_id: int = Field(foreign_key="goals.id", primary_key=True)
    condition_id: int = Field(foreign_key="conditions.id", primary_key=True)
    required_value: bool = Field(default=True)

    goal: Optional[Goal] = Relationship(back_populates="goal_conditions")
    condition: Optional[Condition] = Relationship(back_populates="goal_conditions")


class DayEntry(SQLModel, table=True):
    __tablename__ = "day_entries"

    date: str = Field(primary_key=True)
    note: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    conditions: List["DayCondition"] = Relationship(back_populates="day_entry")


class DayCondition(SQLModel, table=True):
    __tablename__ = "day_conditions"

    date: str = Field(foreign_key="day_entries.date", primary_key=True)
    condition_id: int = Field(foreign_key="conditions.id", primary_key=True)
    value: bool = Field(default=False)

    day_entry: Optional[DayEntry] = Relationship(back_populates="conditions")
    condition: Optional[Condition] = Relationship()


class TagEvent(SQLModel, table=True):
    __tablename__ = "tag_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: str
    tag_id: int = Field(foreign_key="tags.id")
    ts: Optional[datetime] = None
    count: int = Field(default=1)
    note: Optional[str] = None

    tag: Optional[Tag] = Relationship(back_populates="tag_events")
