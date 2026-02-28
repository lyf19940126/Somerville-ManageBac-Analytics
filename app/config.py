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
    homeroom_advisor_id: int
    target_graduating_year: int
    term_id: str
    database_url: str = "sqlite:///data/app.db"


_ENV_LOADED = False


def _load_env_once() -> None:
    global _ENV_LOADED
    if not _ENV_LOADED:
        load_dotenv()
        _ENV_LOADED = True


def _require(name: str, help_text: str | None = None) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    hint = f" {help_text}" if help_text else ""
    raise ConfigError(f"Missing required environment variable: {name}.{hint}")


def _require_int(name: str, help_text: str | None = None) -> int:
    raw = _require(name, help_text)
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"Environment variable {name} must be an integer") from exc


def load_settings() -> Settings:
    _load_env_once()
    return Settings(
        managebac_token=_require("MANAGEBAC_TOKEN", "Set your ManageBac API token in .env."),
        managebac_base_url=_require("MANAGEBAC_BASE_URL", "Example: https://api.managebac.cn").rstrip("/"),
        report_timezone=os.getenv("REPORT_TIMEZONE", "Asia/Shanghai").strip() or "Asia/Shanghai",
        homeroom_advisor_id=_require_int("HOMEROOM_ADVISOR_ID", "Use the advisor numeric ID."),
        target_graduating_year=_require_int("TARGET_GRADUATING_YEAR", "Example: 2028."),
        term_id=_require("TERM_ID", "Use the active term id used by your school in ManageBac."),
    )


def ensure_directories() -> None:
    for path in ("data", "logs", "output/reports"):
        Path(path).mkdir(parents=True, exist_ok=True)
