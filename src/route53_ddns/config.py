from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8080, ge=1, le=65535, validation_alias="PORT")
    poll_interval_seconds: int = Field(
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        ge=10,
        le=86400,
        validation_alias="POLL_INTERVAL_SECONDS",
        description="Seconds between poll cycles (default 4 hours = 14400)",
    )
    checkip_url: str = Field(
        default="https://checkip.amazonaws.com",
        validation_alias="CHECKIP_URL",
    )
    route53_records_file: Path = Field(
        ...,
        validation_alias="ROUTE53_RECORDS_FILE",
        description="Path to a JSON file listing Route53 records (mounted file in Docker)",
    )

    @staticmethod
    def _parse_records_payload(raw: str) -> list[dict[str, Any]]:
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("records file must contain a JSON array")
        return list(data)

    def load_records(self) -> list[Route53RecordConfig]:
        path = self.route53_records_file.expanduser().resolve()
        if not path.is_file():
            raise ValueError(
                f"ROUTE53_RECORDS_FILE does not exist or is not a file: {path}"
            )
        raw = path.read_text(encoding="utf-8")
        items = self._parse_records_payload(raw)
        return [Route53RecordConfig.model_validate(item) for item in items]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
