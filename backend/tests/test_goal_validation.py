import httpx
import pytest
from sqlmodel import create_engine

from app.db import init_db
from app.main import create_app


@pytest.mark.anyio
async def test_goal_rating_target_count_validation(tmp_path):
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
        invalid_create = {
            "name": "Mood",
            "target_window": "day",
            "target_count": 101,
            "scoring_mode": "rating",
        }
        create_resp = await client.post("/goals", json=invalid_create)
        assert create_resp.status_code == 400
        assert "target_count" in create_resp.json()["detail"]

        valid_create = {
            "name": "Walk",
            "target_window": "day",
            "target_count": 1,
            "scoring_mode": "count",
        }
        valid_resp = await client.post("/goals", json=valid_create)
        assert valid_resp.status_code == 201
        goal_id = valid_resp.json()["id"]

        update_resp = await client.put(
            f"/goals/{goal_id}",
            json={"scoring_mode": "rating", "target_count": 0},
        )
        assert update_resp.status_code == 400
        assert "target_count" in update_resp.json()["detail"]
