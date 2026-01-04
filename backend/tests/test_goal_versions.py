from datetime import date, timedelta

import httpx
import pytest
from sqlmodel import Session, create_engine, select

from app.db import init_db
from app.main import create_app
from app.models import GoalVersion


@pytest.mark.anyio
async def test_goal_version_split_and_scoring(tmp_path):
    db_file = tmp_path / "versions.db"
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
        tag_resp = await client.post("/tags", json={"name": "practice"})
        assert tag_resp.status_code == 201
        tag_id = tag_resp.json()["id"]

        goal_payload = {
            "name": "Practice",
            "description": "Daily reps",
            "active": True,
            "target_window": "day",
            "target_count": 1,
            "scoring_mode": "count",
            "tags": [{"tag_id": tag_id, "weight": 1}],
            "conditions": [],
        }
        create_resp = await client.post("/goals", json=goal_payload)
        assert create_resp.status_code == 201
        goal_id = create_resp.json()["id"]

        await client.post(
            f"/days/{today_str}/tag-events",
            json={"tag_id": tag_id, "count": 1},
        )
        await client.post(
            f"/days/{tomorrow_str}/tag-events",
            json={"tag_id": tag_id, "count": 1},
        )

        update_resp = await client.put(
            f"/goals/{goal_id}",
            json={"target_count": 2, "effective_date": tomorrow_str},
        )
        assert update_resp.status_code == 200

        today_resp = await client.get(f"/days/{today_str}")
        assert today_resp.status_code == 200
        today_goal = next(
            goal for goal in today_resp.json()["goals"] if goal["goal_id"] == goal_id
        )
        assert today_goal["target"] == 1
        assert today_goal["status"] == "met"

        tomorrow_resp = await client.get(f"/days/{tomorrow_str}")
        assert tomorrow_resp.status_code == 200
        tomorrow_goal = next(
            goal for goal in tomorrow_resp.json()["goals"] if goal["goal_id"] == goal_id
        )
        assert tomorrow_goal["target"] == 2
        assert tomorrow_goal["status"] == "partial"

    with Session(engine) as session:
        versions = session.exec(
            select(GoalVersion)
            .where(GoalVersion.goal_id == goal_id)
            .order_by(GoalVersion.start_date)
        ).all()
        assert len(versions) == 2
        assert versions[0].start_date == today_str
        assert versions[0].end_date == today_str
        assert versions[1].start_date == tomorrow_str
        assert versions[1].end_date is None
