import httpx
import pytest
from sqlmodel import create_engine

from app.db import init_db
from app.main import create_app


@pytest.mark.anyio
async def test_goals_crud_flow(tmp_path):
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
        tag_resp = await client.post("/tags", json={"name": "health"})
        condition_resp = await client.post("/conditions", json={"name": "slept"})

        assert tag_resp.status_code == 201
        assert condition_resp.status_code == 201

        tag_id = tag_resp.json()["id"]
        condition_id = condition_resp.json()["id"]

        goal_payload = {
            "name": "Workout",
            "description": "Daily workout",
            "active": True,
            "target_window": "day",
            "target_count": 1,
            "scoring_mode": "count",
            "tags": [{"tag_id": tag_id, "weight": 2}],
            "conditions": [
                {"condition_id": condition_id, "required_value": True}
            ],
        }

        create_resp = await client.post("/goals", json=goal_payload)
        assert create_resp.status_code == 201
        created = create_resp.json()
        assert created["name"] == "Workout"
        assert created["tags"][0]["tag"]["id"] == tag_id
        assert created["conditions"][0]["condition"]["id"] == condition_id

        list_resp = await client.get("/goals")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        update_payload = {
            "name": "Workout v2",
            "tags": [],
            "conditions": [
                {"condition_id": condition_id, "required_value": False}
            ],
        }
        update_resp = await client.put(f"/goals/{created['id']}", json=update_payload)
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["name"] == "Workout v2"
        assert updated["tags"] == []
        assert updated["conditions"][0]["required_value"] is False

        delete_resp = await client.delete(f"/goals/{created['id']}")
        assert delete_resp.status_code == 200
        deleted = delete_resp.json()
        assert deleted["active"] is False

        list_after_delete = await client.get("/goals")
        assert list_after_delete.status_code == 200
        assert list_after_delete.json()[0]["active"] is False
