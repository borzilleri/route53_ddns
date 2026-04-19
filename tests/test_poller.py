from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from route53_ddns.config import Route53RecordConfig, Settings, clear_settings_cache
from route53_ddns.poller import fetch_public_ip, manual_update_all, poll_cycle
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


@pytest.mark.asyncio
async def test_manual_update_all_only_updates_out_of_date():
    clear_settings_cache()
    settings = Settings()
    rc0 = Route53RecordConfig(
        hosted_zone_id="Z1",
        record_name="a.example.com.",
        ttl=300,
    )
    rc1 = Route53RecordConfig(
        hosted_zone_id="Z1",
        record_name="b.example.com.",
        ttl=300,
    )
    state = AppState(poll_interval_seconds=settings.poll_interval_seconds)
    state.records.append(RecordRuntime(index=0, config=rc0))
    state.records.append(RecordRuntime(index=1, config=rc1))

    transport = httpx.MockTransport(lambda r: httpx.Response(200, text="203.0.113.1"))
    mock_r53 = MagicMock()
    apply_mock = AsyncMock()

    async def fake_refresh(_r53, st, index):
        async with st.lock:
            st.records[index].route53_ip = (
                "198.51.100.2" if index == 0 else "203.0.113.1"
            )

    with (
        patch("route53_ddns.poller.get_route53_client", return_value=mock_r53),
        patch("route53_ddns.poller.refresh_route53_ip_at", side_effect=fake_refresh),
        patch("route53_ddns.poller.apply_update_at", apply_mock),
    ):
        async with httpx.AsyncClient(transport=transport) as client:
            await manual_update_all(client, state, settings.checkip_url)

    apply_mock.assert_awaited_once()
    call_kw = apply_mock.await_args
    assert call_kw.args[2] == 0

    async with state.lock:
        assert state.current_public_ip == "203.0.113.1"


@pytest.mark.asyncio
async def test_manual_update_all_no_upsert_when_all_match():
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
    apply_mock = AsyncMock()

    async def fake_refresh(_r53, st, _index):
        async with st.lock:
            st.records[0].route53_ip = "203.0.113.1"

    with (
        patch("route53_ddns.poller.get_route53_client", return_value=mock_r53),
        patch("route53_ddns.poller.refresh_route53_ip_at", side_effect=fake_refresh),
        patch("route53_ddns.poller.apply_update_at", apply_mock),
    ):
        async with httpx.AsyncClient(transport=transport) as client:
            await manual_update_all(client, state, settings.checkip_url)

    apply_mock.assert_not_awaited()
