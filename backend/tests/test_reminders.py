from datetime import datetime

from sqlmodel import Session, create_engine, select

from app.db import init_db, set_engine
from app.models import (
    Condition,
    Goal,
    GoalCondition,
    GoalTag,
    Notification,
    ScoringMode,
    Tag,
    TagEvent,
    TargetWindow,
)
from app.services import reminder_service


def test_reminder_creates_notification_for_incomplete_goals(tmp_path):
    db_file = tmp_path / "reminders.db"
    engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    set_engine(engine)
    init_db()

    with Session(engine) as session:
        read_tag = Tag(name="read")
        workout_tag = Tag(name="workout")
        nap_tag = Tag(name="nap")
        session.add_all([read_tag, workout_tag, nap_tag])
        session.commit()
        session.refresh(read_tag)
        session.refresh(workout_tag)
        session.refresh(nap_tag)

        quiet_condition = Condition(name="quiet_house")
        session.add(quiet_condition)
        session.commit()
        session.refresh(quiet_condition)

        read_goal = Goal(
            name="Read",
            description="Read pages",
            active=True,
            target_window=TargetWindow.day,
            target_count=2,
            scoring_mode=ScoringMode.count,
        )
        workout_goal = Goal(
            name="Workout",
            description="Do workouts",
            active=True,
            target_window=TargetWindow.day,
            target_count=1,
            scoring_mode=ScoringMode.count,
        )
        nap_goal = Goal(
            name="Nap",
            description="Take a nap",
            active=True,
            target_window=TargetWindow.day,
            target_count=1,
            scoring_mode=ScoringMode.count,
        )
        session.add_all([read_goal, workout_goal, nap_goal])
        session.commit()
        session.refresh(read_goal)
        session.refresh(workout_goal)
        session.refresh(nap_goal)

        session.add_all(
            [
                GoalTag(goal_id=read_goal.id, tag_id=read_tag.id, weight=1),
                GoalTag(goal_id=workout_goal.id, tag_id=workout_tag.id, weight=1),
                GoalTag(goal_id=nap_goal.id, tag_id=nap_tag.id, weight=1),
                GoalCondition(
                    goal_id=nap_goal.id,
                    condition_id=quiet_condition.id,
                    required_value=True,
                ),
            ]
        )
        session.commit()

        date_str = "2024-02-10"
        session.add_all(
            [
                TagEvent(date=date_str, tag_id=read_tag.id, count=1),
                TagEvent(date=date_str, tag_id=workout_tag.id, count=1),
            ]
        )
        session.commit()

        now = datetime(2024, 2, 10, 8, 0, 0)
        result = reminder_service.run_reminders(session, now=now, force=True)
        assert result["ran"] is True
        assert result["created"] is True

        notifications = session.exec(select(Notification)).all()
        assert len(notifications) == 1
        note = notifications[0]
        assert note.dedupe_key == f"reminder:{date_str}"
        assert "Read" in note.body
        assert "Workout" not in note.body
        assert "Nap" not in note.body

        second = reminder_service.run_reminders(session, now=now, force=True)
        assert second["created"] is False

        notifications_after = session.exec(select(Notification)).all()
        assert len(notifications_after) == 1
