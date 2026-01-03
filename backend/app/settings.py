from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_int(value: Optional[str], default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    if parsed <= 0:
        return default
    return parsed


class Settings:
    def __init__(self) -> None:
        base_dir = Path(__file__).resolve().parents[1]
        default_db_path = base_dir / "data" / "app.db"
        self.db_path = Path(os.getenv("DB_PATH", default_db_path))
        self.db_url = os.getenv("DB_URL")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.reminders_enabled = _parse_bool(os.getenv("REMINDERS_ENABLED"), False)
        self.reminders_cadence_minutes = _parse_int(
            os.getenv("REMINDERS_CADENCE_MINUTES"), 1440
        )

    @property
    def database_url(self) -> str:
        if self.db_url:
            return self.db_url
        return f"sqlite:///{self.db_path}"


settings = Settings()
