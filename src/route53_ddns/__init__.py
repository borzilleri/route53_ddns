"""Route53 dynamic DNS service."""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError, version


def _resolve_version() -> str:
    env = os.environ.get("APP_VERSION", "").strip()
    if env:
        return env
    try:
        return version("route53-ddns")
    except PackageNotFoundError:
        return "0.0.0"


__version__ = _resolve_version()
