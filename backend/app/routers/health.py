from __future__ import annotations

from fastapi import APIRouter

from ..schemas import LlmHealthResponse
from ..services import ollama_client

router = APIRouter()


@router.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@router.get("/llm/health", response_model=LlmHealthResponse)
def llm_health_check() -> LlmHealthResponse:
    return LlmHealthResponse(**ollama_client.health_check())
