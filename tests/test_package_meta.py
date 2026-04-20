from __future__ import annotations

import pytest

from route53_ddns.package_meta import (
    FALLBACK_GITHUB_REPOSITORY,
    github_repository_slug_from_metadata,
    parse_github_repository_url,
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/foo/bar", "foo/bar"),
        ("https://github.com/foo/bar.git", "foo/bar"),
        ("https://www.github.com/org/name/", "org/name"),
        ("https://example.com/foo/bar", None),
    ],
)
def test_parse_github_repository_url(url: str, expected: str | None) -> None:
    assert parse_github_repository_url(url) == expected


def test_github_repository_slug_from_metadata_matches_upstream() -> None:
    slug = github_repository_slug_from_metadata()
    assert slug == FALLBACK_GITHUB_REPOSITORY
