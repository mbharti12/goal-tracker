from __future__ import annotations

import os
from typing import Dict, List

import httpx
from fastapi import HTTPException, status

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")


def _ollama_unreachable_message(base_url: str) -> str:
    return f"Ollama is not running at {base_url}. Start it with `ollama serve`."


def health_check(timeout: float = 2.0) -> Dict[str, object]:
    base_url = OLLAMA_BASE_URL
    payload: Dict[str, object] = {
        "reachable": False,
        "model": DEFAULT_MODEL,
        "base_url": base_url,
        "error": None,
    }
    try:
        response = httpx.get(
            f"{base_url}/api/version",
            timeout=timeout,
        )
    except httpx.RequestError as exc:
        payload["error"] = _ollama_unreachable_message(base_url)
        return payload

    if response.status_code != 200:
        payload["error"] = f"Ollama error: {response.text}"
        return payload

    payload["reachable"] = True
    return payload


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
            detail=_ollama_unreachable_message(OLLAMA_BASE_URL),
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
