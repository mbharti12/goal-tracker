from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect
from sqlmodel import SQLModel, Session, create_engine

from .models import GoalRating
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


def get_session():
    with Session(engine) as session:
        yield session
