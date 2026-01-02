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
        condition_resp = await client.post("/conditions", json={"name": "with_family"})

        assert brush_tag.status_code == 201
        assert hindi_tag.status_code == 201
        assert workout_tag.status_code == 201
        assert condition_resp.status_code == 201

        brush_id = brush_tag.json()["id"]
        hindi_id = hindi_tag.json()["id"]
        workout_id = workout_tag.json()["id"]
        condition_id = condition_resp.json()["id"]

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
        assert workout_goal["progress"] == 3
        assert workout_goal["status"] == "met"

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
        assert day10["applicable_goals"] == 2
        assert day10["met_goals"] == 2
        assert day10["completion_ratio"] == 1
        assert day10["conditions"] == []
        tags_by_name = {tag["name"]: tag for tag in day10["tags"]}
        assert tags_by_name["brush"]["count"] == 2
        assert tags_by_name["hindi"]["count"] == 1
        assert tags_by_name["workout"]["count"] == 1

        day11 = next(item for item in calendar if item["date"] == "2024-01-11")
        assert day11["conditions"] == [
            {"condition_id": condition_id, "name": "with_family", "value": True}
        ]
        assert day11["completion_ratio"] == pytest.approx(2 / 3)
