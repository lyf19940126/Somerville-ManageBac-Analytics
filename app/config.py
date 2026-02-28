from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(ValueError):
    """Raised when required configuration is missing."""


@dataclass(frozen=True)
class Settings:
    managebac_token: str
    managebac_base_url: str
    report_timezone: str
    homeroom_name: str
    homeroom_id: int | None
    term_id: str
    database_url: str = "sqlite:///data/app.db"


_ENV_LOADED = False


def _load_env_once() -> None:
    global _ENV_LOADED
    if not _ENV_LOADED:
        load_dotenv()
        _ENV_LOADED = True


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def _optional_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"Environment variable {name} must be an integer when set") from exc


def load_settings(require_term_id: bool = True) -> Settings:
    _load_env_once()

    term_id = _require("TERM_ID") if require_term_id else os.getenv("TERM_ID", "").strip()
    return Settings(
        managebac_token=_require("MANAGEBAC_TOKEN"),
        managebac_base_url=_require("MANAGEBAC_BASE_URL").rstrip("/"),
        report_timezone=os.getenv("REPORT_TIMEZONE", "Asia/Shanghai").strip() or "Asia/Shanghai",
        homeroom_name=os.getenv("HOMEROOM_NAME", "Somerville").strip() or "Somerville",
        homeroom_id=_optional_int("HOMEROOM_ID"),
        term_id=term_id,
    )


def ensure_directories() -> None:
    for path in ("data", "logs", "output/reports"):
        Path(path).mkdir(parents=True, exist_ok=True)
