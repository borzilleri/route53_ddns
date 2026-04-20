"""GitHub Releases API helpers for update-available checks."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from packaging.version import InvalidVersion, Version

logger = logging.getLogger(__name__)


def split_github_repository(value: str) -> tuple[str, str]:
    parts = value.strip().split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("repository must be owner/repo")
    return parts[0], parts[1]


def normalize_version_tag(tag: str) -> str:
    t = tag.strip()
    if len(t) > 1 and t.startswith("v"):
        return t[1:]
    return t


def parse_version(tag: str) -> Version | None:
    try:
        return Version(normalize_version_tag(tag))
    except InvalidVersion:
        return None


def is_remote_newer(remote_tag: str, current_version: str) -> bool:
    rv = parse_version(remote_tag)
    cv = parse_version(current_version)
    if rv is None or cv is None:
        return False
    return rv > cv


async def fetch_latest_release(
    client: httpx.AsyncClient,
    api_base: str,
    owner: str,
    repo: str,
) -> tuple[str, str]:
    """Return (raw tag_name, html_url) from GET .../releases/latest."""
    url = f"{api_base}/repos/{owner}/{repo}/releases/latest"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "route53-ddns",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    r = await client.get(url, headers=headers)
    r.raise_for_status()
    data: dict[str, Any] = r.json()
    tag = data.get("tag_name")
    html_url = data.get("html_url")
    if not isinstance(tag, str) or not isinstance(html_url, str):
        raise ValueError("unexpected GitHub API response shape")
    return tag, html_url
