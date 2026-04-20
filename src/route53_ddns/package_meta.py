"""Read package metadata (e.g. canonical GitHub URL from pyproject)."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, metadata
from urllib.parse import urlparse

# Used when [project.urls] Repository is missing or unparsable.
FALLBACK_GITHUB_REPOSITORY = "borzilleri/route53_ddns"


def parse_github_repository_url(url: str) -> str | None:
    """Parse ``https://github.com/owner/repo`` (optional ``.git``) to ``owner/repo``."""
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return None
    host = (parsed.netloc or "").lower()
    if host not in ("github.com", "www.github.com"):
        return None
    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return None


def github_repository_slug_from_metadata() -> str:
    """Return owner/repo from installed package Project-URL Repository, or fallback."""
    try:
        meta = metadata("route53-ddns")
    except PackageNotFoundError:
        return FALLBACK_GITHUB_REPOSITORY

    for line in meta.get_all("Project-URL") or []:
        if "," not in line:
            continue
        label, rest = line.split(",", 1)
        if label.strip() != "Repository":
            continue
        slug = parse_github_repository_url(rest.strip())
        if slug:
            return slug
    return FALLBACK_GITHUB_REPOSITORY
