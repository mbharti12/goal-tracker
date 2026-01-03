import httpx
import pytest
from sqlmodel import create_engine

from app.db import init_db
from app.main import create_app
from app.services import ollama_client


@pytest.mark.anyio
async def test_health_check(tmp_path):
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
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_llm_health_reachable(tmp_path, respx_mock):
    db_file = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    app = create_app(engine_override=engine)
    init_db()

    respx_mock.get(f"{ollama_client.OLLAMA_BASE_URL}/api/version").mock(
        return_value=httpx.Response(200, json={"version": "0.1.0"})
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/llm/health")

    assert response.status_code == 200
    data = response.json()
    assert data["reachable"] is True
    assert data["model"] == ollama_client.DEFAULT_MODEL
    assert data["base_url"] == ollama_client.OLLAMA_BASE_URL
    assert data["error"] is None


@pytest.mark.anyio
async def test_llm_health_unreachable(tmp_path, respx_mock):
    db_file = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    app = create_app(engine_override=engine)
    init_db()

    request = httpx.Request(
        "GET", f"{ollama_client.OLLAMA_BASE_URL}/api/version"
    )
    respx_mock.get(f"{ollama_client.OLLAMA_BASE_URL}/api/version").mock(
        side_effect=httpx.ConnectError("boom", request=request)
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/llm/health")

    assert response.status_code == 200
    data = response.json()
    assert data["reachable"] is False
    assert data["model"] == ollama_client.DEFAULT_MODEL
    assert data["base_url"] == ollama_client.OLLAMA_BASE_URL
    assert "ollama serve" in data["error"].lower()
