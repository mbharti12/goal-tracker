from __future__ import annotations

import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        base_dir = Path(__file__).resolve().parents[1]
        default_db_path = base_dir / "data" / "app.db"
        self.db_path = Path(os.getenv("DB_PATH", default_db_path))
        self.db_url = os.getenv("DB_URL")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")

    @property
    def database_url(self) -> str:
        if self.db_url:
            return self.db_url
        return f"sqlite:///{self.db_path}"


settings = Settings()
