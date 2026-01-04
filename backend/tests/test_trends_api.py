import httpx
import pytest
from sqlmodel import create_engine

from app.db import init_db
from app.main import create_app


@pytest.mark.anyio
async def test_goal_trend_day_bucket(tmp_path):
    db_file = tmp_path / "trend.db"
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
        tag_resp = await client.post("/tags", json={"name": "read"})
        assert tag_resp.status_code == 201
        tag_id = tag_resp.json()["id"]

        goal_payload = {
            "name": "Read",
            "target_window": "day",
            "target_count": 1,
            "scoring_mode": "count",
            "tags": [{"tag_id": tag_id, "weight": 1}],
            "conditions": [],
        }
        goal_resp = await client.post("/goals", json=goal_payload)
        assert goal_resp.status_code == 201
        goal_id = goal_resp.json()["id"]

        await client.post(
            "/days/2024-01-02/tag-events",
            json={"tag_id": tag_id, "count": 1},
        )

        trend_resp = await client.get(
            f"/goals/{goal_id}/trend",
            params={"start": "2024-01-01", "end": "2024-01-03", "bucket": "day"},
        )
        assert trend_resp.status_code == 200
        data = trend_resp.json()
        assert data["goal_id"] == goal_id
        assert data["bucket"] == "day"
        assert len(data["points"]) == 3
        point = next(item for item in data["points"] if item["date"] == "2024-01-02")
        assert point["progress"] == 1
        assert point["status"] == "met"


@pytest.mark.anyio
async def test_compare_trends_correlation(tmp_path):
    db_file = tmp_path / "compare.db"
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
        tag_ids = []
        for name in ["a", "b", "c"]:
            tag_resp = await client.post("/tags", json={"name": name})
            assert tag_resp.status_code == 201
            tag_ids.append(tag_resp.json()["id"])

        goal_ids = []
        for idx, tag_id in enumerate(tag_ids):
            goal_payload = {
                "name": f"Goal {idx}",
                "target_window": "day",
                "target_count": 2 if idx < 2 else 1,
                "scoring_mode": "count",
                "tags": [{"tag_id": tag_id, "weight": 1}],
                "conditions": [],
            }
            goal_resp = await client.post("/goals", json=goal_payload)
            assert goal_resp.status_code == 201
            goal_ids.append(goal_resp.json()["id"])

        dates = [
            "2024-01-01",
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
            "2024-01-05",
        ]
        counts = [0, 1, 2, 1, 0]
        for date_str, count in zip(dates, counts):
            if count:
                await client.post(
                    f"/days/{date_str}/tag-events",
                    json={"tag_id": tag_ids[0], "count": count},
                )
                await client.post(
                    f"/days/{date_str}/tag-events",
                    json={"tag_id": tag_ids[1], "count": count},
                )
            await client.post(
                f"/days/{date_str}/tag-events",
                json={"tag_id": tag_ids[2], "count": 1},
            )

        compare_resp = await client.post(
            "/trends/compare",
            json={
                "goal_ids": goal_ids,
                "start": "2024-01-01",
                "end": "2024-01-05",
                "bucket": "day",
            },
        )
        assert compare_resp.status_code == 200
        data = compare_resp.json()
        comparisons = data["comparisons"]

        pair_ab = next(
            item
            for item in comparisons
            if item["goal_id_a"] == goal_ids[0] and item["goal_id_b"] == goal_ids[1]
        )
        assert pair_ab["n"] == 5
        assert pair_ab["correlation"] == pytest.approx(1.0, abs=1e-6)

        pair_ac = next(
            item
            for item in comparisons
            if item["goal_id_a"] == goal_ids[0] and item["goal_id_b"] == goal_ids[2]
        )
        assert pair_ac["correlation"] is None
