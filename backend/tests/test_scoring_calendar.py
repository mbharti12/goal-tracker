import httpx
import pytest
from sqlmodel import create_engine

from app.db import init_db
from app.main import create_app


@pytest.mark.anyio
async def test_scoring_and_calendar(tmp_path):
    db_file = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    app = create_app(engine_override=engine)
    init_db()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        brush_tag = await client.post("/tags", json={"name": "brush"})
        hindi_tag = await client.post("/tags", json={"name": "hindi"})
        workout_tag = await client.post("/tags", json={"name": "workout"})
        meditate_tag = await client.post("/tags", json={"name": "meditate"})
        condition_resp = await client.post("/conditions", json={"name": "with_family"})

        assert brush_tag.status_code == 201
        assert hindi_tag.status_code == 201
        assert workout_tag.status_code == 201
        assert condition_resp.status_code == 201
        assert meditate_tag.status_code == 201

        brush_id = brush_tag.json()["id"]
        hindi_id = hindi_tag.json()["id"]
        workout_id = workout_tag.json()["id"]
        condition_id = condition_resp.json()["id"]
        meditate_id = meditate_tag.json()["id"]

        goals = [
            {
                "name": "Brush",
                "description": "Brush teeth",
                "active": True,
                "target_window": "day",
                "target_count": 2,
                "scoring_mode": "count",
                "tags": [{"tag_id": brush_id, "weight": 1}],
                "conditions": [],
            },
            {
                "name": "Speak Hindi",
                "description": "Practice with family",
                "active": True,
                "target_window": "day",
                "target_count": 1,
                "scoring_mode": "count",
                "tags": [{"tag_id": hindi_id, "weight": 1}],
                "conditions": [
                    {"condition_id": condition_id, "required_value": True}
                ],
            },
            {
                "name": "Workout",
                "description": "Weekly workout",
                "active": True,
                "target_window": "week",
                "target_count": 3,
                "scoring_mode": "count",
                "tags": [{"tag_id": workout_id, "weight": 1}],
                "conditions": [],
            },
            {
                "name": "Meditate",
                "description": "Monthly meditation",
                "active": True,
                "target_window": "month",
                "target_count": 4,
                "scoring_mode": "count",
                "tags": [{"tag_id": meditate_id, "weight": 1}],
                "conditions": [],
            },
        ]

        for goal_payload in goals:
            resp = await client.post("/goals", json=goal_payload)
            assert resp.status_code == 201

        await client.put(
            "/days/2024-01-11/conditions",
            json={"conditions": [{"condition_id": condition_id, "value": True}]},
        )

        await client.post(
            "/days/2024-01-10/tag-events",
            json={"tag_id": brush_id, "count": 1},
        )
        await client.post(
            "/days/2024-01-10/tag-events",
            json={"tag_id": brush_id, "count": 1},
        )
        await client.post(
            "/days/2024-01-10/tag-events",
            json={"tag_id": hindi_id, "count": 1},
        )
        await client.post(
            "/days/2024-01-08/tag-events",
            json={"tag_id": workout_id, "count": 1},
        )
        await client.post(
            "/days/2024-01-10/tag-events",
            json={"tag_id": workout_id, "count": 1},
        )
        await client.post(
            "/days/2024-01-14/tag-events",
            json={"tag_id": workout_id, "count": 1},
        )
        await client.post(
            "/days/2024-01-11/tag-events",
            json={"tag_id": hindi_id, "count": 1},
        )
        await client.post(
            "/days/2024-01-15/tag-events",
            json={"tag_id": workout_id, "count": 1},
        )
        await client.post(
            "/days/2024-01-05/tag-events",
            json={"tag_id": meditate_id, "count": 1},
        )
        await client.post(
            "/days/2024-01-10/tag-events",
            json={"tag_id": meditate_id, "count": 1},
        )
        await client.post(
            "/days/2024-01-20/tag-events",
            json={"tag_id": meditate_id, "count": 1},
        )

        day_resp = await client.get("/days/2024-01-10")
        assert day_resp.status_code == 200
        goals_by_name = {goal["goal_name"]: goal for goal in day_resp.json()["goals"]}

        brush_goal = goals_by_name["Brush"]
        assert brush_goal["applicable"] is True
        assert brush_goal["progress"] == 2
        assert brush_goal["status"] == "met"

        hindi_goal = goals_by_name["Speak Hindi"]
        assert hindi_goal["applicable"] is False
        assert hindi_goal["status"] == "na"
        assert hindi_goal["progress"] == 0

        workout_goal = goals_by_name["Workout"]
        assert workout_goal["target_window"] == "week"
        assert workout_goal["progress"] == 2
        assert workout_goal["status"] == "partial"

        meditate_goal = goals_by_name["Meditate"]
        assert meditate_goal["target_window"] == "month"
        assert meditate_goal["progress"] == 2
        assert meditate_goal["status"] == "partial"

        next_week_day = await client.get("/days/2024-01-15")
        assert next_week_day.status_code == 200
        next_goals = {
            goal["goal_name"]: goal for goal in next_week_day.json()["goals"]
        }
        next_workout = next_goals["Workout"]
        assert next_workout["progress"] == 1
        assert next_workout["status"] == "partial"

        calendar_resp = await client.get(
            "/calendar", params={"start": "2024-01-10", "end": "2024-01-11"}
        )
        assert calendar_resp.status_code == 200
        calendar = calendar_resp.json()
        assert len(calendar) == 2

        day10 = next(item for item in calendar if item["date"] == "2024-01-10")
        assert day10["applicable_goals"] == 3
        assert day10["met_goals"] == 1
        assert day10["completion_ratio"] == pytest.approx(1 / 3)
        assert day10["conditions"] == []
        tags_by_name = {tag["name"]: tag for tag in day10["tags"]}
        assert tags_by_name["brush"]["count"] == 2
        assert tags_by_name["hindi"]["count"] == 1
        assert tags_by_name["workout"]["count"] == 1

        day11 = next(item for item in calendar if item["date"] == "2024-01-11")
        assert day11["conditions"] == [
            {"condition_id": condition_id, "name": "with_family", "value": True}
        ]
        assert day11["completion_ratio"] == pytest.approx(1 / 4)


@pytest.mark.anyio
async def test_calendar_summary_filters_target_windows(tmp_path):
    db_file = tmp_path / "summary.db"
    engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    app = create_app(engine_override=engine)
    init_db()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        daily_tag = await client.post("/tags", json={"name": "daily"})
        weekly_tag = await client.post("/tags", json={"name": "weekly"})
        monthly_tag = await client.post("/tags", json={"name": "monthly"})

        assert daily_tag.status_code == 201
        assert weekly_tag.status_code == 201
        assert monthly_tag.status_code == 201

        daily_id = daily_tag.json()["id"]
        weekly_id = weekly_tag.json()["id"]
        monthly_id = monthly_tag.json()["id"]

        goals = [
            {
                "name": "Daily goal",
                "description": "Daily target",
                "active": True,
                "target_window": "day",
                "target_count": 1,
                "scoring_mode": "count",
                "tags": [{"tag_id": daily_id, "weight": 1}],
                "conditions": [],
            },
            {
                "name": "Weekly goal",
                "description": "Weekly target",
                "active": True,
                "target_window": "week",
                "target_count": 2,
                "scoring_mode": "count",
                "tags": [{"tag_id": weekly_id, "weight": 1}],
                "conditions": [],
            },
            {
                "name": "Monthly goal",
                "description": "Monthly target",
                "active": True,
                "target_window": "month",
                "target_count": 3,
                "scoring_mode": "count",
                "tags": [{"tag_id": monthly_id, "weight": 1}],
                "conditions": [],
            },
        ]

        for goal_payload in goals:
            resp = await client.post("/goals", json=goal_payload)
            assert resp.status_code == 201

        await client.post(
            "/days/2024-01-03/tag-events",
            json={"tag_id": daily_id, "count": 1},
        )

        await client.post(
            "/days/2024-01-01/tag-events",
            json={"tag_id": weekly_id, "count": 1},
        )
        await client.post(
            "/days/2024-01-02/tag-events",
            json={"tag_id": weekly_id, "count": 1},
        )
        await client.post(
            "/days/2024-01-09/tag-events",
            json={"tag_id": weekly_id, "count": 1},
        )

        await client.post(
            "/days/2024-01-05/tag-events",
            json={"tag_id": monthly_id, "count": 1},
        )
        await client.post(
            "/days/2024-01-10/tag-events",
            json={"tag_id": monthly_id, "count": 1},
        )

        summary_resp = await client.get(
            "/calendar/summary", params={"start": "2024-01-01", "end": "2024-01-14"}
        )
        assert summary_resp.status_code == 200
        summary = summary_resp.json()

        assert len(summary["days"]) == 14
        assert len(summary["weeks"]) == 2
        assert len(summary["months"]) == 1

        day3 = next(item for item in summary["days"] if item["date"] == "2024-01-03")
        assert day3["applicable_goals"] == 1
        assert day3["met_goals"] == 1

        day4 = next(item for item in summary["days"] if item["date"] == "2024-01-04")
        assert day4["applicable_goals"] == 1
        assert day4["met_goals"] == 0

        week1 = next(item for item in summary["weeks"] if item["start"] == "2024-01-01")
        assert week1["applicable_goals"] == 1
        assert week1["met_goals"] == 1

        week2 = next(item for item in summary["weeks"] if item["start"] == "2024-01-08")
        assert week2["applicable_goals"] == 1
        assert week2["met_goals"] == 0

        month = next(item for item in summary["months"] if item["start"] == "2024-01-01")
        assert month["applicable_goals"] == 1
        assert month["met_goals"] == 0
