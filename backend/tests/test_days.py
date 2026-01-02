import httpx
import pytest
from sqlmodel import create_engine

from app.db import init_db
from app.main import create_app


@pytest.mark.anyio
async def test_daily_logging_flow(tmp_path):
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
        condition_resp = await client.post("/conditions", json={"name": "slept"})
        assert condition_resp.status_code == 201
        condition_id = condition_resp.json()["id"]

        date = "2024-01-10"

        note_resp = await client.put(f"/days/{date}/note", json={"note": "Felt good"})
        assert note_resp.status_code == 200
        assert note_resp.json()["note"] == "Felt good"

        note_resp_repeat = await client.put(
            f"/days/{date}/note", json={"note": "Felt good"}
        )
        assert note_resp_repeat.status_code == 200
        assert note_resp_repeat.json()["note"] == "Felt good"

        note_resp_update = await client.put(
            f"/days/{date}/note", json={"note": "Updated note"}
        )
        assert note_resp_update.status_code == 200
        assert note_resp_update.json()["note"] == "Updated note"

        conditions_payload = {
            "conditions": [{"condition_id": condition_id, "value": True}]
        }
        conditions_resp = await client.put(
            f"/days/{date}/conditions", json=conditions_payload
        )
        assert conditions_resp.status_code == 200
        conditions_data = conditions_resp.json()
        assert conditions_data == [
            {"condition_id": condition_id, "name": "slept", "value": True}
        ]

        tag_by_name_resp = await client.post(
            f"/days/{date}/tag-events",
            json={"tag_name": "coffee", "count": 2, "note": "morning"},
        )
        assert tag_by_name_resp.status_code == 201
        tag_by_name = tag_by_name_resp.json()
        assert tag_by_name["tag_name"] == "coffee"
        assert tag_by_name["count"] == 2
        tag_id = tag_by_name["tag_id"]

        tag_by_id_resp = await client.post(
            f"/days/{date}/tag-events",
            json={"tag_id": tag_id, "count": 1},
        )
        assert tag_by_id_resp.status_code == 201

        day_resp = await client.get(f"/days/{date}")
        assert day_resp.status_code == 200
        day_data = day_resp.json()
        assert set(day_data.keys()) == {
            "day_entry",
            "conditions",
            "tag_events",
            "goals",
        }
        assert day_data["day_entry"]["date"] == date
        assert day_data["day_entry"]["note"] == "Updated note"
        assert day_data["conditions"] == conditions_data
        assert len(day_data["tag_events"]) == 2
        assert day_data["goals"] == []

        delete_resp = await client.delete(f"/tag-events/{tag_by_name['id']}")
        assert delete_resp.status_code == 200
        assert delete_resp.json() == {"deleted": True}

        day_after_delete = await client.get(f"/days/{date}")
        assert day_after_delete.status_code == 200
        assert len(day_after_delete.json()["tag_events"]) == 1
