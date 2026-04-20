from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default time between public-IP checks and Route53 reconciliation.
DEFAULT_POLL_INTERVAL_SECONDS = 14_400  # 4 hours


def default_txt_record_name(a_record_fqdn: str) -> str:
    """Derive companion TXT name: _ddns-last-update.<labels of A record>."""
    name = a_record_fqdn.strip().rstrip(".")
    if not name:
        raise ValueError("empty record name")
    return f"_ddns-last-update.{name}."


def api_host_label(record_name: str) -> str:
    """Hostname/FQDN for API display (strip trailing dot from Route53 FQDN)."""
    return record_name.strip().rstrip(".")


class Route53RecordConfig(BaseModel):
    """One A record and its companion TXT (update timestamp)."""

    hosted_zone_id: str = Field(..., description="Route53 hosted zone ID")
    record_name: str = Field(..., description="FQDN for A record, trailing dot recommended")
    ttl: int = Field(default=300, ge=60, le=86400)
    txt_record_name: str | None = Field(
        default=None,
        description="Override companion TXT FQDN; default derived from record_name",
    )

    @field_validator("record_name", "txt_record_name", mode="before")
    @classmethod
    def strip_name(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
        return v

    def resolved_txt_name(self) -> str:
        if self.txt_record_name:
            n = self.txt_record_name.strip()
            return n if n.endswith(".") else f"{n}."
        return default_txt_record_name(self.record_name)


class NotificationsConfig(BaseModel):
    """Apprise notification targets (see https://github.com/caronc/apprise)."""

    apprise_urls: list[str] = Field(default_factory=list)


class FileConfig(BaseModel):
    """Application settings loaded from CONFIG_FILE (YAML)."""

    poll_interval_seconds: int = Field(
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        ge=10,
        le=86400,
    )
    checkip_url: str = Field(default="https://checkip.amazonaws.com")
    records: list[Route53RecordConfig]
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)


class Settings(BaseSettings):
    """Process environment: bind address and path to YAML config."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8080, ge=1, le=65535, validation_alias="PORT")
    config_file: Path = Field(
        default=Path("config.yaml"),
        validation_alias="CONFIG_FILE",
        description="Path to YAML config (poll interval, checkip URL, records, notifications)",
    )
    github_repository: str | None = Field(
        default=None,
        validation_alias="GITHUB_REPOSITORY",
        description="owner/repo for GitHub Releases API (optional; enables update-available footer)",
    )
    github_api_base: str = Field(
        default="https://api.github.com",
        validation_alias="GITHUB_API_BASE",
        description="GitHub API base URL (override for tests or GitHub Enterprise)",
    )

    @field_validator("github_repository", mode="before")
    @classmethod
    def empty_github_repo(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("github_repository", mode="after")
    @classmethod
    def validate_github_repository(cls, v: str | None) -> str | None:
        if v is None:
            return None
        parts = v.strip().split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError("GITHUB_REPOSITORY must be in the form owner/repo")
        return f"{parts[0].strip()}/{parts[1].strip()}"

    @field_validator("github_api_base", mode="after")
    @classmethod
    def strip_api_base(cls, v: str) -> str:
        return v.rstrip("/")

    def resolved_config_path(self) -> Path:
        return self.config_file.expanduser().resolve()


def load_file_config(path: Path) -> FileConfig:
    """Load and validate YAML from ``path``."""
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"CONFIG_FILE does not exist or is not a file: {path}")
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if data is None:
        raise ValueError("config file is empty")
    if not isinstance(data, dict):
        raise ValueError("config file must contain a YAML mapping at the top level")
    return FileConfig.model_validate(data)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
