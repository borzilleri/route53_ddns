from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from route53_ddns.config import get_settings
from route53_ddns.main import build_app


@pytest.fixture
def client():
    async def noop_poller(*args, **kwargs):
        return None

    with (
        patch("route53_ddns.main.verify_credentials", lambda: None),
        patch("route53_ddns.main.poller_loop", noop_poller),
    ):
        app = build_app(get_settings())
        with TestClient(app) as c:
            yield c


def test_index_ok(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert "Route53 dynamic DNS" in r.text
    assert "dyn.example.com" in r.text
