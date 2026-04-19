from __future__ import annotations

import asyncio
import ipaddress
import logging
from datetime import datetime, timedelta, timezone
import httpx

from route53_ddns.config import FileConfig, api_host_label
from route53_ddns.notifications import send_poll_cycle_notification
from route53_ddns.route53_ops import get_route53_client, list_a_record_ip, upsert_a_and_txt
from route53_ddns.state import AppState, utcnow

logger = logging.getLogger(__name__)


def next_scheduled(last: datetime, interval: int) -> datetime:
    base = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
    return base + timedelta(seconds=interval)


async def fetch_public_ip(client: httpx.AsyncClient, url: str) -> str:
    resp = await client.get(url)
    resp.raise_for_status()
    text = resp.text.strip()
    try:
        ipaddress.IPv4Address(text)
    except ipaddress.AddressValueError as e:
        raise ValueError(f"checkip returned non-IPv4: {text!r}") from e
    return text


async def refresh_route53_ip_at(r53, state: AppState, index: int) -> None:
    async with state.lock:
        rec = state.records[index]
        zone_id = rec.config.hosted_zone_id
        name = rec.config.record_name
    ip_val = await asyncio.to_thread(list_a_record_ip, r53, zone_id, name)
    async with state.lock:
        state.records[index].route53_ip = ip_val


async def apply_update_at(
    r53,
    state: AppState,
    index: int,
    public_ip: str,
) -> None:
    now = utcnow()
    async with state.lock:
        rec = state.records[index]
        zone_id = rec.config.hosted_zone_id
        a_name = rec.config.record_name
        txt_name = rec.config.resolved_txt_name()
        ttl = rec.config.ttl
    await asyncio.to_thread(
        upsert_a_and_txt,
        r53,
        zone_id,
        a_name,
        public_ip,
        txt_name,
        now,
        ttl,
    )
    async with state.lock:
        state.records[index].route53_ip = public_ip
        state.records[index].last_dns_update_at = now
    logger.info(
        "Updated Route53 A+TXT zone=%s name=%s -> %s",
        zone_id,
        a_name,
        public_ip,
    )


async def _notify_poll_cycle(
    apprise_urls: list[str],
    updated_hosts: list[str],
    errors: list[str],
) -> None:
    if not apprise_urls or (not updated_hosts and not errors):
        return
    await asyncio.to_thread(
        send_poll_cycle_notification,
        apprise_urls,
        updated_hosts,
        errors,
    )


async def poll_cycle(
    http: httpx.AsyncClient,
    file_config: FileConfig,
    state: AppState,
) -> None:
    r53 = get_route53_client()
    interval = state.poll_interval_seconds
    checkip_url = file_config.checkip_url
    apprise_urls = file_config.notifications.apprise_urls

    try:
        public_ip = await fetch_public_ip(http, checkip_url)
    except (httpx.HTTPError, ValueError) as e:
        msg = f"checkip failed: {e}"
        logger.error(msg)
        now = utcnow()
        async with state.lock:
            state.last_error = msg
            state.last_check_at = now
            state.next_check_at = next_scheduled(now, interval)
        await _notify_poll_cycle(apprise_urls, [], [msg])
        return

    async with state.lock:
        state.current_public_ip = public_ip
        state.last_error = None
        n = len(state.records)

    cycle_errors: list[str] = []
    updated_hosts: list[str] = []

    for idx in range(n):
        try:
            await refresh_route53_ip_at(r53, state, idx)
            async with state.lock:
                aws_ip = state.records[idx].route53_ip
            needs = aws_ip is None or aws_ip != public_ip
            if needs:
                await apply_update_at(r53, state, idx, public_ip)
                async with state.lock:
                    hn = api_host_label(state.records[idx].config.record_name)
                updated_hosts.append(hn)
            else:
                async with state.lock:
                    name = state.records[idx].config.record_name
                logger.info(
                    "No Route53 change needed for %s (already %s)",
                    name,
                    public_ip,
                )
        except Exception as e:  # noqa: BLE001
            err_s = f"record index {idx}: {e}"
            logger.error("record index %s: %s", idx, e, exc_info=True)
            cycle_errors.append(err_s)
            async with state.lock:
                state.last_error = str(e)

    done = utcnow()
    async with state.lock:
        state.last_check_at = done
        state.next_check_at = next_scheduled(done, interval)

    await _notify_poll_cycle(apprise_urls, updated_hosts, cycle_errors)


async def manual_update_index(
    http: httpx.AsyncClient,
    state: AppState,
    checkip_url: str,
    index: int,
) -> None:
    public_ip = await fetch_public_ip(http, checkip_url)
    r53 = get_route53_client()
    async with state.lock:
        if index < 0 or index >= len(state.records):
            raise IndexError("invalid record index")

    await refresh_route53_ip_at(r53, state, index)
    async with state.lock:
        aws_ip = state.records[index].route53_ip
    if aws_ip == public_ip:
        logger.info("manual update skipped: already %s", public_ip)
        done = utcnow()
        async with state.lock:
            state.current_public_ip = public_ip
            state.last_check_at = done
            state.next_check_at = next_scheduled(done, state.poll_interval_seconds)
        return

    await apply_update_at(r53, state, index, public_ip)
    done = utcnow()
    async with state.lock:
        state.current_public_ip = public_ip
        state.last_check_at = done
        state.next_check_at = next_scheduled(done, state.poll_interval_seconds)


async def manual_update_all(
    http: httpx.AsyncClient,
    state: AppState,
    checkip_url: str,
) -> None:
    public_ip = await fetch_public_ip(http, checkip_url)
    r53 = get_route53_client()
    async with state.lock:
        n = len(state.records)
        interval = state.poll_interval_seconds
        state.last_error = None

    for idx in range(n):
        try:
            await refresh_route53_ip_at(r53, state, idx)
            async with state.lock:
                aws_ip = state.records[idx].route53_ip
            if aws_ip == public_ip:
                async with state.lock:
                    name = state.records[idx].config.record_name
                logger.info(
                    "manual update all: skip %s (already %s)",
                    name,
                    public_ip,
                )
                continue
            await apply_update_at(r53, state, idx, public_ip)
        except Exception as e:  # noqa: BLE001
            logger.error(
                "manual update all record index %s: %s",
                idx,
                e,
                exc_info=True,
            )
            async with state.lock:
                state.last_error = str(e)

    done = utcnow()
    async with state.lock:
        state.current_public_ip = public_ip
        state.last_check_at = done
        state.next_check_at = next_scheduled(done, interval)


async def poller_loop(
    http: httpx.AsyncClient,
    file_config: FileConfig,
    state: AppState,
    stop: asyncio.Event,
) -> None:
    interval = file_config.poll_interval_seconds
    while not stop.is_set():
        await poll_cycle(http, file_config, state)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            continue
