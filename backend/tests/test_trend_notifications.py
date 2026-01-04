from datetime import datetime, timedelta

from sqlmodel import Session, create_engine, select

from app.db import init_db, set_engine
from app.models import (
    Goal,
    GoalTag,
    GoalVersion,
    GoalVersionTag,
    Notification,
    ScoringMode,
    Tag,
    TagEvent,
    TargetWindow,
)
from app.services import reminder_service


def test_trend_notification_dedupe(tmp_path):
    db_file = tmp_path / "trend.db"
    engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    set_engine(engine)
    init_db()

    with Session(engine) as session:
        tag = Tag(name="habit")
        session.add(tag)
        session.commit()
        session.refresh(tag)

        goal = Goal(
            name="Daily habit",
            description="Keep it up",
            active=True,
            target_window=TargetWindow.day,
            target_count=1,
            scoring_mode=ScoringMode.count,
        )
        session.add(goal)
        session.commit()
        session.refresh(goal)

        session.add(GoalTag(goal_id=goal.id, tag_id=tag.id, weight=1))
        session.commit()

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
        session.add(
            GoalVersionTag(
                goal_version_id=version.id,
                tag_id=tag.id,
                weight=1,
            )
        )
        session.commit()

        now = datetime(2024, 2, 15, 8, 0, 0)
        end_date = now.date()
        for offset in range(7, 14):
            event_date = (end_date - timedelta(days=offset)).isoformat()
            session.add(TagEvent(date=event_date, tag_id=tag.id, count=1))
        session.commit()

        result = reminder_service.run_reminders(session, now=now, force=True)
        assert result["ran"] is True

        trends = session.exec(
            select(Notification).where(Notification.type == "trend")
        ).all()
        assert len(trends) == 1
        assert trends[0].dedupe_key == f"trend:avg_drop:{goal.id}:{end_date.isoformat()}"

        second = reminder_service.run_reminders(session, now=now, force=True)
        assert second["ran"] is True

        trends_after = session.exec(
            select(Notification).where(Notification.type == "trend")
        ).all()
        assert len(trends_after) == 1
