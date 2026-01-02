from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
