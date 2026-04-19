from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from route53_ddns.config import Route53RecordConfig

from route53_ddns.config import DEFAULT_POLL_INTERVAL_SECONDS, api_host_label


def record_needs_update(
    current_public_ip: str | None,
    route53_ip: str | None,
) -> bool:
    """True when the per-row Update control should be enabled (not in sync)."""
    return not (
        current_public_ip is not None
        and route53_ip is not None
        and current_public_ip == route53_ip
    )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RecordRuntime:
    index: int
    config: "Route53RecordConfig"
    route53_ip: str | None = None
    last_dns_update_at: datetime | None = None


@dataclass
class AppState:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    current_public_ip: str | None = None
    last_check_at: datetime | None = None
    next_check_at: datetime | None = None
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS
    records: list[RecordRuntime] = field(default_factory=list)
    last_error: str | None = None

    def snapshot_for_template(self) -> dict:
        """Sync read for Jinja (call under lock from async route)."""
        rows = []
        for r in self.records:
            rows.append(
                {
                    "index": r.index,
                    "record_name": r.config.record_name,
                    "route53_ip": r.route53_ip,
                    "last_dns_update_at": r.last_dns_update_at,
                    "needs_update": record_needs_update(
                        self.current_public_ip,
                        r.route53_ip,
                    ),
                }
            )
        any_row_out_of_date = any(row["needs_update"] for row in rows)
        return {
            "current_public_ip": self.current_public_ip,
            "last_check_at": self.last_check_at,
            "next_check_at": self.next_check_at,
            "poll_interval_seconds": self.poll_interval_seconds,
            "records": rows,
            "last_error": self.last_error,
            "any_row_out_of_date": any_row_out_of_date,
        }

    def status_api_dict(self) -> dict:
        """JSON-serializable status for GET /api/status (call under lock)."""
        record_rows: list[dict] = []
        last_any: datetime | None = None
        for r in self.records:
            lu = r.last_dns_update_at
            if lu is not None and (last_any is None or lu > last_any):
                last_any = lu
            record_rows.append(
                {
                    "host": api_host_label(r.config.record_name),
                    "lastUpdated": lu.isoformat() if lu is not None else None,
                }
            )
        return {
            "lastUpdated": last_any.isoformat() if last_any is not None else None,
            "records": record_rows,
        }
