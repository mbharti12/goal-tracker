import httpx
import pytest
from sqlmodel import create_engine

from app.db import init_db
from app.main import create_app


@pytest.mark.anyio
async def test_condition_archiving_flow(tmp_path):
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
        create_resp = await client.post("/conditions", json={"name": "focused"})
        assert create_resp.status_code == 201
        created = create_resp.json()
        assert created["active"] is True

        deactivate_resp = await client.put(
            f"/conditions/{created['id']}/deactivate"
        )
        assert deactivate_resp.status_code == 200
        assert deactivate_resp.json()["active"] is False

        list_active = await client.get("/conditions")
        assert list_active.status_code == 200
        assert list_active.json() == []

        list_all = await client.get("/conditions?include_inactive=true")
        assert list_all.status_code == 200
        assert list_all.json()[0]["active"] is False

        reactivate_resp = await client.put(
            f"/conditions/{created['id']}/reactivate"
        )
        assert reactivate_resp.status_code == 200
        assert reactivate_resp.json()["active"] is True


@pytest.mark.anyio
async def test_condition_reactivate_on_create(tmp_path):
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
        create_resp = await client.post("/conditions", json={"name": "rested"})
        assert create_resp.status_code == 201
        created = create_resp.json()

        deactivate_resp = await client.put(
            f"/conditions/{created['id']}/deactivate"
        )
        assert deactivate_resp.status_code == 200

        recreate_resp = await client.post("/conditions", json={"name": "rested"})
        assert recreate_resp.status_code == 201
        assert recreate_resp.json()["id"] == created["id"]
        assert recreate_resp.json()["active"] is True
