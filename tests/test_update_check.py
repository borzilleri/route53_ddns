from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from route53_ddns.config import clear_settings_cache
from route53_ddns.main import create_app


@pytest.fixture
def client():
    async def noop_poller(*args, **kwargs):
        return None

    with (
        patch("route53_ddns.main.verify_credentials", lambda: None),
        patch("route53_ddns.main.poller_loop", noop_poller),
    ):
        app = create_app()
        with TestClient(app) as c:
            yield c


@pytest.fixture
def client_github(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/testrepo")
    clear_settings_cache()

    async def noop_poller(*args, **kwargs):
        return None

    with (
        patch("route53_ddns.main.verify_credentials", lambda: None),
        patch("route53_ddns.main.poller_loop", noop_poller),
    ):
        app = create_app()
        with TestClient(app) as c:
            yield c

    clear_settings_cache()


def test_update_check_without_github_repo(client):
    r = client.get("/api/update-check")
    assert r.status_code == 200
    data = r.json()
    assert data["github_repository_configured"] is False
    assert data["update_available"] is False
    assert "app_version" in data


@respx.mock
def test_update_check_newer_release_available(client_github, monkeypatch):
    monkeypatch.setattr("route53_ddns.__version__", "1.0.0")
    respx.get("https://api.github.com/repos/acme/testrepo/releases/latest").mock(
        return_value=httpx.Response(
            200,
            json={
                "tag_name": "v2.0.0",
                "html_url": "https://github.com/acme/testrepo/releases/tag/v2.0.0",
            },
        )
    )
    r = client_github.get("/api/update-check")
    assert r.status_code == 200
    data = r.json()
    assert data["github_repository_configured"] is True
    assert data["update_available"] is True
    assert data["latest_version"] == "2.0.0"
    assert data["release_url"].endswith("/releases/tag/v2.0.0")


@respx.mock
def test_update_check_same_version_not_flagged(client_github, monkeypatch):
    monkeypatch.setattr("route53_ddns.__version__", "1.0.0")
    respx.get("https://api.github.com/repos/acme/testrepo/releases/latest").mock(
        return_value=httpx.Response(
            200,
            json={
                "tag_name": "v1.0.0",
                "html_url": "https://github.com/acme/testrepo/releases/tag/v1.0.0",
            },
        )
    )
    r = client_github.get("/api/update-check")
    assert r.status_code == 200
    data = r.json()
    assert data["update_available"] is False
    assert data["latest_version"] == "1.0.0"


@respx.mock
def test_update_check_older_release_not_flagged(client_github, monkeypatch):
    monkeypatch.setattr("route53_ddns.__version__", "2.0.0")
    respx.get("https://api.github.com/repos/acme/testrepo/releases/latest").mock(
        return_value=httpx.Response(
            200,
            json={
                "tag_name": "v1.0.0",
                "html_url": "https://github.com/acme/testrepo/releases/tag/v1.0.0",
            },
        )
    )
    r = client_github.get("/api/update-check")
    assert r.status_code == 200
    data = r.json()
    assert data["update_available"] is False


@respx.mock
def test_update_check_http_error(client_github, monkeypatch):
    monkeypatch.setattr("route53_ddns.__version__", "1.0.0")
    respx.get("https://api.github.com/repos/acme/testrepo/releases/latest").mock(
        return_value=httpx.Response(404)
    )
    r = client_github.get("/api/update-check")
    assert r.status_code == 200
    data = r.json()
    assert data["update_available"] is False
    assert "error" in data
    assert "404" in data["error"]


def test_static_update_footer_js(client):
    r = client.get("/static/update_footer.js")
    assert r.status_code == 200
    assert b"fetch(\"/api/update-check\")" in r.content
