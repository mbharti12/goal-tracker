from datetime import date, timedelta

import httpx
import pytest
from sqlmodel import create_engine

from app.db import init_db
from app.main import create_app


@pytest.mark.anyio
async def test_tag_impacts_respects_versions_and_excludes_rating(tmp_path):
    db_file = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    app = create_app(engine_override=engine)
    init_db()

    today = date.today()
    tomorrow = today + timedelta(days=1)
    today_str = today.isoformat()
    tomorrow_str = tomorrow.isoformat()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        tag_one_resp = await client.post("/tags", json={"name": "stretch"})
        assert tag_one_resp.status_code == 201
        tag_one_id = tag_one_resp.json()["id"]

        tag_two_resp = await client.post("/tags", json={"name": "salad"})
        assert tag_two_resp.status_code == 201
        tag_two_id = tag_two_resp.json()["id"]

        goal_one_payload = {
            "name": "Mobility",
            "description": "Stretch daily",
            "active": True,
            "target_window": "day",
            "target_count": 1,
            "scoring_mode": "count",
            "tags": [{"tag_id": tag_one_id, "weight": 1}],
            "conditions": [],
        }
        goal_one_resp = await client.post("/goals", json=goal_one_payload)
        assert goal_one_resp.status_code == 201
        goal_one_id = goal_one_resp.json()["id"]

        goal_two_payload = {
            "name": "Eat well",
            "description": "Weekly nutrition",
            "active": True,
            "target_window": "week",
            "target_count": 5,
            "scoring_mode": "count",
            "tags": [
                {"tag_id": tag_one_id, "weight": 3},
                {"tag_id": tag_two_id, "weight": 2},
            ],
            "conditions": [],
        }
        goal_two_resp = await client.post("/goals", json=goal_two_payload)
        assert goal_two_resp.status_code == 201
        goal_two_id = goal_two_resp.json()["id"]

        rating_payload = {
            "name": "Mood",
            "description": "Daily check-in",
            "active": True,
            "target_window": "day",
            "target_count": 60,
            "scoring_mode": "rating",
            "tags": [{"tag_id": tag_one_id, "weight": 5}],
            "conditions": [],
        }
        rating_resp = await client.post("/goals", json=rating_payload)
        assert rating_resp.status_code == 201
        rating_goal_id = rating_resp.json()["id"]

        update_resp = await client.put(
            f"/goals/{goal_one_id}",
            json={
                "tags": [{"tag_id": tag_one_id, "weight": 4}],
                "effective_date": tomorrow_str,
            },
        )
        assert update_resp.status_code == 200

        impacts_today = await client.get(f"/days/{today_str}/tag-impacts")
        assert impacts_today.status_code == 200
        impacts_today_json = impacts_today.json()

        tag_one_today = next(
            item for item in impacts_today_json if item["tag_id"] == tag_one_id
        )
        weights_today = {goal["goal_id"]: goal["weight"] for goal in tag_one_today["goals"]}
        assert weights_today[goal_one_id] == 1
        assert weights_today[goal_two_id] == 3
        assert rating_goal_id not in weights_today

        tag_two_today = next(
            item for item in impacts_today_json if item["tag_id"] == tag_two_id
        )
        assert tag_two_today["goals"][0]["goal_id"] == goal_two_id
        assert tag_two_today["goals"][0]["weight"] == 2
        assert tag_two_today["goals"][0]["target_window"] == "week"

        impacts_tomorrow = await client.get(f"/days/{tomorrow_str}/tag-impacts")
        assert impacts_tomorrow.status_code == 200
        impacts_tomorrow_json = impacts_tomorrow.json()

        tag_one_tomorrow = next(
            item for item in impacts_tomorrow_json if item["tag_id"] == tag_one_id
        )
        weights_tomorrow = {
            goal["goal_id"]: goal["weight"] for goal in tag_one_tomorrow["goals"]
        }
        assert weights_tomorrow[goal_one_id] == 4
        assert weights_tomorrow[goal_two_id] == 3
