from datetime import datetime, timedelta

import httpx
import pytest
from sqlmodel import Session, create_engine

from app.db import init_db
from app.main import create_app
from app.models import Notification


@pytest.mark.anyio
async def test_notifications_list_and_mark_read(tmp_path):
    db_file = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    app = create_app(engine_override=engine)
    init_db()

    base_time = datetime(2024, 2, 1, 12, 0, 0)
    older_time = base_time - timedelta(days=1)
    newer_time = base_time + timedelta(hours=2)

    with Session(engine) as session:
        read_notification = Notification(
            type="reminder",
            title="Read one",
            body="Already read",
            created_at=base_time,
            read_at=base_time,
        )
        older_unread = Notification(
            type="reminder",
            title="Older unread",
            body="Old",
            created_at=older_time,
        )
        newer_unread = Notification(
            type="reminder",
            title="Newer unread",
            body="New",
            created_at=newer_time,
        )
        session.add(read_notification)
        session.add(older_unread)
        session.add(newer_unread)
        session.commit()
        session.refresh(read_notification)
        session.refresh(older_unread)
        session.refresh(newer_unread)
        older_unread_id = older_unread.id

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        unread_resp = await client.get("/notifications")
        assert unread_resp.status_code == 200
        unread_titles = [item["title"] for item in unread_resp.json()]
        assert unread_titles == ["Newer unread", "Older unread"]

        all_resp = await client.get("/notifications?unread_only=false")
        assert all_resp.status_code == 200
        all_titles = [item["title"] for item in all_resp.json()]
        assert all_titles == ["Newer unread", "Read one", "Older unread"]

        mark_resp = await client.post(f"/notifications/{older_unread_id}/read")
        assert mark_resp.status_code == 200
        mark_data = mark_resp.json()
        assert mark_data["id"] == older_unread_id
        assert mark_data["read_at"] is not None

        unread_after = await client.get("/notifications")
        assert unread_after.status_code == 200
        unread_after_titles = [item["title"] for item in unread_after.json()]
        assert unread_after_titles == ["Newer unread"]
