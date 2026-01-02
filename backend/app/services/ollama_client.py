from __future__ import annotations

import os
from typing import Dict, List

import httpx
from fastapi import HTTPException, status

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")


def chat(model: str, messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    try:
        response = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=30,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ollama is not running. Start it with `ollama serve`.",
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Ollama error: {response.text}",
        )

    data = response.json()
    message = data.get("message") or {}
    content = message.get("content")
    if not content:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Ollama response missing content.",
        )
    return content
