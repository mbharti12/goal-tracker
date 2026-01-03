import json

import httpx
import pytest
from sqlmodel import create_engine

from app.db import init_db
from app.main import create_app
from app.services import ollama_client


@pytest.mark.anyio
async def test_review_query_and_filter(tmp_path, respx_mock):
    db_file = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    app = create_app(engine_override=engine)
    init_db()

    plan_payload = {
        "start_date": "2024-01-10",
        "end_date": "2024-01-10",
        "last_n_days": None,
        "days_of_week": None,
        "conditions_any": None,
        "conditions_all": None,
        "goals": None,
        "intent": "summary",
    }
    respx_mock.post(f"{ollama_client.OLLAMA_BASE_URL}/api/chat").mock(
        side_effect=[
            httpx.Response(
                200, json={"message": {"content": json.dumps(plan_payload)}}
            ),
            httpx.Response(200, json={"message": {"content": "Summary output"}}),
        ]
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        tag_resp = await client.post("/tags", json={"name": "workout"})
        assert tag_resp.status_code == 201
        tag_id = tag_resp.json()["id"]

        goal_resp = await client.post(
            "/goals",
            json={
                "name": "Workout",
                "description": "Daily movement",
                "active": True,
                "target_window": "day",
                "target_count": 1,
                "scoring_mode": "count",
                "tags": [{"tag_id": tag_id, "weight": 1}],
                "conditions": [],
            },
        )
        assert goal_resp.status_code == 201

        await client.put("/days/2024-01-10/note", json={"note": "Felt good"})
        await client.post(
            "/days/2024-01-10/tag-events",
            json={"tag_id": tag_id, "count": 1},
        )

        review_resp = await client.post(
            "/review/query", json={"prompt": "Summarize yesterday."}
        )
        assert review_resp.status_code == 200
        review_data = review_resp.json()
        assert review_data["answer"] == "Summary output"
        assert review_data["debug"]["plan"]["start_date"] == "2024-01-10"
        assert review_data["debug"]["days_included"] == 1
        assert review_data["debug"]["truncated"] is False

        filter_resp = await client.post(
            "/review/filter",
            json={"start_date": "2024-01-10", "end_date": "2024-01-10"},
        )
        assert filter_resp.status_code == 200
        context = filter_resp.json()["context"]
        assert context["date_range"] == {"start": "2024-01-10", "end": "2024-01-10"}
        assert len(context["days"]) == 1
        assert context["days"][0]["note"] == "Felt good"


@pytest.mark.anyio
async def test_review_query_invalid_plan_falls_back(tmp_path, respx_mock):
    db_file = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    app = create_app(engine_override=engine)
    init_db()

    respx_mock.post(f"{ollama_client.OLLAMA_BASE_URL}/api/chat").mock(
        side_effect=[
            httpx.Response(200, json={"message": {"content": "not json"}}),
            httpx.Response(
                200,
                json={
                    "message": {
                        "content": '{"intent": "summary", "last_n_days": "oops"}'
                    }
                },
            ),
            httpx.Response(200, json={"message": {"content": "Fallback summary"}}),
        ]
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        review_resp = await client.post(
            "/review/query", json={"prompt": "Give me a recap."}
        )
        assert review_resp.status_code == 200
        review_data = review_resp.json()
        assert review_data["answer"] == "Fallback summary"
        assert review_data["debug"]["plan"]["last_n_days"] == 14
        assert review_data["debug"]["plan"]["intent"] == "summary"
