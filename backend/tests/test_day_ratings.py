import httpx
import pytest
from sqlmodel import create_engine

from app.db import init_db
from app.main import create_app


@pytest.mark.anyio
async def test_day_ratings_flow(tmp_path):
    db_file = tmp_path / "ratings.db"
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
        goal_payload = {
            "name": "Mood",
            "target_window": "day",
            "target_count": 80,
            "scoring_mode": "rating",
        }
        goal_resp = await client.post("/goals", json=goal_payload)
        assert goal_resp.status_code == 201
        goal_id = goal_resp.json()["id"]

        date = "2024-01-12"
        rating_payload = {
            "ratings": [
                {"goal_id": goal_id, "rating": 88, "note": "solid day"}
            ]
        }
        rating_resp = await client.put(
            f"/days/{date}/ratings", json=rating_payload
        )
        assert rating_resp.status_code == 200
        assert rating_resp.json() == [
            {"goal_id": goal_id, "rating": 88, "note": "solid day"}
        ]

        day_resp = await client.get(f"/days/{date}")
        assert day_resp.status_code == 200
        assert day_resp.json()["goal_ratings"] == [
            {"goal_id": goal_id, "rating": 88, "note": "solid day"}
        ]


@pytest.mark.anyio
async def test_rating_goal_statuses(tmp_path):
    db_file = tmp_path / "ratings-status.db"
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
        condition_resp = await client.post("/conditions", json={"name": "rested"})
        assert condition_resp.status_code == 201
        condition_id = condition_resp.json()["id"]

        goal_payload = {
            "name": "Mood",
            "target_window": "day",
            "target_count": 80,
            "scoring_mode": "rating",
            "conditions": [{"condition_id": condition_id, "required_value": True}],
        }
        goal_resp = await client.post("/goals", json=goal_payload)
        assert goal_resp.status_code == 201
        goal_id = goal_resp.json()["id"]

        async def set_condition(date_str: str, value: bool) -> None:
            resp = await client.put(
                f"/days/{date_str}/conditions",
                json={"conditions": [{"condition_id": condition_id, "value": value}]},
            )
            assert resp.status_code == 200

        async def get_goal_status(date_str: str) -> dict:
            day_resp = await client.get(f"/days/{date_str}")
            assert day_resp.status_code == 200
            return next(
                goal
                for goal in day_resp.json()["goals"]
                if goal["goal_id"] == goal_id
            )

        date_met = "2024-01-10"
        await set_condition(date_met, True)
        rating_resp = await client.put(
            f"/days/{date_met}/ratings",
            json={"ratings": [{"goal_id": goal_id, "rating": 90}]},
        )
        assert rating_resp.status_code == 200
        met_goal = await get_goal_status(date_met)
        assert met_goal["status"] == "met"
        assert met_goal["progress"] == 90
        assert isinstance(met_goal["progress"], float)
        assert met_goal["samples"] == 1
        assert met_goal["window_days"] == 1
        assert met_goal["target_window"] == "day"
        assert met_goal["scoring_mode"] == "rating"

        date_partial = "2024-01-11"
        await set_condition(date_partial, True)
        rating_resp = await client.put(
            f"/days/{date_partial}/ratings",
            json={"ratings": [{"goal_id": goal_id, "rating": 50}]},
        )
        assert rating_resp.status_code == 200
        partial_goal = await get_goal_status(date_partial)
        assert partial_goal["status"] == "missed"
        assert partial_goal["progress"] == 50
        assert partial_goal["samples"] == 1
        assert partial_goal["window_days"] == 1

        date_missed = "2024-01-12"
        await set_condition(date_missed, True)
        missed_goal = await get_goal_status(date_missed)
        assert missed_goal["status"] == "missed"
        assert missed_goal["progress"] == 0
        assert missed_goal["samples"] == 0
        assert missed_goal["window_days"] == 1

        date_na = "2024-01-13"
        await set_condition(date_na, False)
        rating_resp = await client.put(
            f"/days/{date_na}/ratings",
            json={"ratings": [{"goal_id": goal_id, "rating": 100}]},
        )
        assert rating_resp.status_code == 200
        na_goal = await get_goal_status(date_na)
        assert na_goal["status"] == "na"
        assert na_goal["applicable"] is False
        assert na_goal["progress"] == 0
        assert na_goal["samples"] == 0
        assert na_goal["window_days"] == 0


@pytest.mark.anyio
async def test_day_ratings_invalid_value(tmp_path):
    db_file = tmp_path / "ratings-invalid.db"
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
        goal_payload = {
            "name": "Energy",
            "target_window": "day",
            "target_count": 50,
            "scoring_mode": "rating",
        }
        goal_resp = await client.post("/goals", json=goal_payload)
        assert goal_resp.status_code == 201
        goal_id = goal_resp.json()["id"]

        invalid_resp = await client.put(
            "/days/2024-01-13/ratings",
            json={"ratings": [{"goal_id": goal_id, "rating": 0}]},
        )
        assert invalid_resp.status_code == 422


@pytest.mark.anyio
async def test_rating_goal_week_window_average(tmp_path):
    db_file = tmp_path / "ratings-week.db"
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
        goal_payload = {
            "name": "Weekly mood",
            "target_window": "week",
            "target_count": 25,
            "scoring_mode": "rating",
        }
        goal_resp = await client.post("/goals", json=goal_payload)
        assert goal_resp.status_code == 201
        goal_id = goal_resp.json()["id"]

        await client.put(
            "/days/2024-01-08/ratings",
            json={"ratings": [{"goal_id": goal_id, "rating": 70}]},
        )
        await client.put(
            "/days/2024-01-10/ratings",
            json={"ratings": [{"goal_id": goal_id, "rating": 90}]},
        )

        day_resp = await client.get("/days/2024-01-14")
        assert day_resp.status_code == 200
        goal = next(
            entry for entry in day_resp.json()["goals"] if entry["goal_id"] == goal_id
        )
        assert goal["scoring_mode"] == "rating"
        assert goal["samples"] == 2
        assert goal["window_days"] == 7
        assert goal["progress"] == pytest.approx((70 + 90) / 7)
        assert isinstance(goal["progress"], float)
        assert goal["status"] == "missed"


@pytest.mark.anyio
async def test_rating_goal_month_window_average(tmp_path):
    db_file = tmp_path / "ratings-month.db"
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
        goal_payload = {
            "name": "Monthly mood",
            "target_window": "month",
            "target_count": 30,
            "scoring_mode": "rating",
        }
        goal_resp = await client.post("/goals", json=goal_payload)
        assert goal_resp.status_code == 201
        goal_id = goal_resp.json()["id"]

        await client.put(
            "/days/2024-02-02/ratings",
            json={"ratings": [{"goal_id": goal_id, "rating": 60}]},
        )
        await client.put(
            "/days/2024-02-04/ratings",
            json={"ratings": [{"goal_id": goal_id, "rating": 80}]},
        )

        day_resp = await client.get("/days/2024-02-05")
        assert day_resp.status_code == 200
        goal = next(
            entry for entry in day_resp.json()["goals"] if entry["goal_id"] == goal_id
        )
        assert goal["scoring_mode"] == "rating"
        assert goal["samples"] == 2
        assert goal["window_days"] == 5
        assert goal["progress"] == pytest.approx((60 + 80) / 5)
        assert isinstance(goal["progress"], float)
        assert goal["status"] == "missed"
