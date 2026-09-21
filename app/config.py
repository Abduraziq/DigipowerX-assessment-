from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "neo-cloudz-local-inference"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "6.0"))
    queue_limit: int = int(os.getenv("QUEUE_LIMIT", "3"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "2"))
    sqlite_path: Path = Path(os.getenv("USAGE_DB_PATH", "./data/usage.db"))
    default_customer: str = os.getenv("DEFAULT_CUSTOMER", "demo")


settings = Settings()
