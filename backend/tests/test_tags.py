import httpx
import pytest
from sqlmodel import create_engine

from app.db import init_db
from app.main import create_app


@pytest.mark.anyio
async def test_tag_archiving_flow(tmp_path):
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
        create_resp = await client.post("/tags", json={"name": "focus"})
        assert create_resp.status_code == 201
        created = create_resp.json()
        assert created["active"] is True

        deactivate_resp = await client.put(f"/tags/{created['id']}/deactivate")
        assert deactivate_resp.status_code == 200
        assert deactivate_resp.json()["active"] is False

        list_active = await client.get("/tags")
        assert list_active.status_code == 200
        assert list_active.json() == []

        list_all = await client.get("/tags?include_inactive=true")
        assert list_all.status_code == 200
        assert list_all.json()[0]["active"] is False

        recreate_resp = await client.post("/tags", json={"name": "focus"})
        assert recreate_resp.status_code == 201
        assert recreate_resp.json()["id"] == created["id"]
        assert recreate_resp.json()["active"] is True


@pytest.mark.anyio
async def test_tag_events_keep_name_after_archive(tmp_path):
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
        create_resp = await client.post("/tags", json={"name": "reading"})
        tag_id = create_resp.json()["id"]

        date = "2024-02-01"
        event_resp = await client.post(
            f"/days/{date}/tag-events",
            json={"tag_id": tag_id, "count": 1},
        )
        assert event_resp.status_code == 201

        deactivate_resp = await client.put(f"/tags/{tag_id}/deactivate")
        assert deactivate_resp.status_code == 200

        day_resp = await client.get(f"/days/{date}")
        assert day_resp.status_code == 200
        events = day_resp.json()["tag_events"]
        assert events[0]["tag_name"] == "reading"


@pytest.mark.anyio
async def test_tag_hard_delete_guardrails(tmp_path):
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
        unused_resp = await client.post("/tags", json={"name": "unused"})
        unused_id = unused_resp.json()["id"]

        delete_resp = await client.delete(f"/tags/{unused_id}")
        assert delete_resp.status_code == 200

        in_use_resp = await client.post("/tags", json={"name": "in-use"})
        in_use_id = in_use_resp.json()["id"]
        date = "2024-02-02"
        await client.post(
            f"/days/{date}/tag-events",
            json={"tag_id": in_use_id, "count": 1},
        )

        delete_in_use = await client.delete(f"/tags/{in_use_id}")
        assert delete_in_use.status_code == 409


@pytest.mark.anyio
async def test_tag_category_create_update_and_reactivate(tmp_path):
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
        create_resp = await client.post(
            "/tags", json={"name": "focus", "category": "Mind"}
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        assert created["category"] == "Mind"

        update_resp = await client.put(
            f"/tags/{created['id']}", json={"category": "Work"}
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["category"] == "Work"

        deactivate_resp = await client.put(f"/tags/{created['id']}/deactivate")
        assert deactivate_resp.status_code == 200

        reactivate_resp = await client.post(
            "/tags", json={"name": "focus", "category": "Personal"}
        )
        assert reactivate_resp.status_code == 201
        assert reactivate_resp.json()["active"] is True
        assert reactivate_resp.json()["category"] == "Personal"
