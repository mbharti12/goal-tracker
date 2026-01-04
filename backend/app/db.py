from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect
from sqlmodel import SQLModel, Session, create_engine, select

from .models import (
    Goal,
    GoalCondition,
    GoalRating,
    GoalTag,
    GoalVersion,
    GoalVersionCondition,
    GoalVersionTag,
)
from .settings import settings


def _ensure_sqlite_dir() -> None:
    if settings.db_url:
        return
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)


def create_db_engine() -> object:
    _ensure_sqlite_dir()
    return create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )


engine = create_db_engine()


def set_engine(new_engine: object) -> None:
    global engine
    engine = new_engine


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _ensure_goal_ratings_table()
    _ensure_tags_active_column()
    _ensure_goal_versions()


def _ensure_tags_active_column() -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.connect() as conn:
        result = conn.exec_driver_sql("PRAGMA table_info(tags)")
        columns = {row[1] for row in result}

    if "active" in columns:
        return

    with engine.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE tags ADD COLUMN active BOOLEAN NOT NULL DEFAULT 1"
        )


def _ensure_goal_ratings_table() -> None:
    inspector = inspect(engine)
    if "goal_ratings" in inspector.get_table_names():
        return
    SQLModel.metadata.create_all(engine, tables=[GoalRating.__table__])


def _ensure_goal_versions() -> None:
    with Session(engine) as session:
        goals = session.exec(select(Goal)).all()
        if not goals:
            return

        existing_goal_ids = set(session.exec(select(GoalVersion.goal_id)).all())
        for goal in goals:
            if goal.id is None or goal.id in existing_goal_ids:
                continue

            version = GoalVersion(
                goal_id=goal.id,
                start_date="0001-01-01",
                end_date=None,
                target_window=goal.target_window,
                target_count=goal.target_count,
                scoring_mode=goal.scoring_mode,
            )
            session.add(version)
            session.flush()

            tags = session.exec(
                select(GoalTag).where(GoalTag.goal_id == goal.id)
            ).all()
            for tag in tags:
                session.add(
                    GoalVersionTag(
                        goal_version_id=version.id,
                        tag_id=tag.tag_id,
                        weight=tag.weight,
                    )
                )

            conditions = session.exec(
                select(GoalCondition).where(GoalCondition.goal_id == goal.id)
            ).all()
            for condition in conditions:
                session.add(
                    GoalVersionCondition(
                        goal_version_id=version.id,
                        condition_id=condition.condition_id,
                        required_value=condition.required_value,
                    )
                )

        session.commit()


def get_session():
    with Session(engine) as session:
        yield session
