from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from route53_ddns.config import Route53RecordConfig, Settings, clear_settings_cache
from route53_ddns.poller import fetch_public_ip, poll_cycle
from route53_ddns.state import AppState, RecordRuntime


@pytest.mark.asyncio
async def test_fetch_public_ip_ok():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, text=" 203.0.113.1 \n"))
    async with httpx.AsyncClient(transport=transport) as client:
        ip = await fetch_public_ip(client, "https://example.com")
    assert ip == "203.0.113.1"


@pytest.mark.asyncio
async def test_fetch_public_ip_invalid():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, text="not-an-ip"))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ValueError):
            await fetch_public_ip(client, "https://example.com")


@pytest.mark.asyncio
async def test_poll_cycle_updates_when_mismatch(monkeypatch):
    clear_settings_cache()
    settings = Settings()
    rc = Route53RecordConfig(
        hosted_zone_id="Z1",
        record_name="dyn.example.com.",
        ttl=300,
    )
    state = AppState(poll_interval_seconds=settings.poll_interval_seconds)
    state.records.append(RecordRuntime(index=0, config=rc))

    transport = httpx.MockTransport(lambda r: httpx.Response(200, text="203.0.113.1"))
    mock_r53 = MagicMock()
    mock_r53.get_paginator.return_value.paginate.return_value = iter(
        [
            {
                "ResourceRecordSets": [
                    {
                        "Name": "dyn.example.com.",
                        "Type": "A",
                        "ResourceRecords": [{"Value": "198.51.100.2"}],
                    }
                ]
            }
        ]
    )

    with patch("route53_ddns.poller.get_route53_client", return_value=mock_r53):
        async with httpx.AsyncClient(transport=transport) as client:
            await poll_cycle(client, settings, state, settings.checkip_url)

    mock_r53.change_resource_record_sets.assert_called_once()
    batch = mock_r53.change_resource_record_sets.call_args.kwargs["ChangeBatch"]["Changes"]
    assert len(batch) == 2
    async with state.lock:
        assert state.records[0].route53_ip == "203.0.113.1"
        assert state.records[0].last_dns_update_at is not None


@pytest.mark.asyncio
async def test_poll_cycle_no_change_when_match(monkeypatch):
    clear_settings_cache()
    settings = Settings()
    rc = Route53RecordConfig(hosted_zone_id="Z1", record_name="dyn.example.com.", ttl=300)
    state = AppState(poll_interval_seconds=settings.poll_interval_seconds)
    state.records.append(RecordRuntime(index=0, config=rc))

    transport = httpx.MockTransport(lambda r: httpx.Response(200, text="203.0.113.1"))
    mock_r53 = MagicMock()
    mock_r53.get_paginator.return_value.paginate.return_value = iter(
        [
            {
                "ResourceRecordSets": [
                    {
                        "Name": "dyn.example.com.",
                        "Type": "A",
                        "ResourceRecords": [{"Value": "203.0.113.1"}],
                    }
                ]
            }
        ]
    )

    with patch("route53_ddns.poller.get_route53_client", return_value=mock_r53):
        async with httpx.AsyncClient(transport=transport) as client:
            await poll_cycle(client, settings, state, settings.checkip_url)

    mock_r53.change_resource_record_sets.assert_not_called()
