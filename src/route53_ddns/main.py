from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from route53_ddns.config import FileConfig, Settings, clear_settings_cache, get_settings, load_file_config
from route53_ddns.github_release import (
    fetch_latest_release,
    is_remote_newer,
    normalize_version_tag,
    split_github_repository,
)
from route53_ddns.logging_config import setup_logging
from route53_ddns.poller import manual_update_all, manual_update_index, poller_loop
from route53_ddns.route53_ops import verify_credentials
from route53_ddns.state import AppState, RecordRuntime

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@dataclass
class UpdateCheckRuntime:
    """In-memory cache for GET /api/update-check (GitHub Releases)."""

    ttl_seconds: float = 600.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    cached_at_monotonic: float = 0.0
    cached_payload: dict | None = None


def build_app(settings: Settings, file_config: FileConfig) -> FastAPI:
    records_cfg = file_config.records
    state = AppState(poll_interval_seconds=file_config.poll_interval_seconds)
    for i, rc in enumerate(records_cfg):
        state.records.append(RecordRuntime(index=i, config=rc))

    stop_event: asyncio.Event | None = None
    poller_task: asyncio.Task | None = None
    http_client: httpx.AsyncClient | None = None
    update_check_runtime = UpdateCheckRuntime()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal stop_event, poller_task, http_client
        setup_logging()
        try:
            await asyncio.to_thread(verify_credentials)
        except Exception as e:  # noqa: BLE001
            logger.error("AWS credential check failed: %s", e, exc_info=True)
            raise
        stop_event = asyncio.Event()
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
        )
        poller_task = asyncio.create_task(
            poller_loop(http_client, file_config, state, stop_event),
        )
        logger.info("Started poller (interval=%ss)", file_config.poll_interval_seconds)
        yield
        if stop_event:
            stop_event.set()
        if poller_task:
            await poller_task
        if http_client:
            await http_client.aclose()
        logger.info("Shutdown complete")

    app = FastAPI(title="route53-ddns", lifespan=lifespan)
    app.mount(
        "/static",
        StaticFiles(directory=str(BASE_DIR / "static")),
        name="static",
    )

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        async with state.lock:
            ctx = state.snapshot_for_template()
        return templates.TemplateResponse(request, "index.html", ctx)

    @app.get("/api/status")
    async def api_status() -> dict:
        async with state.lock:
            return state.status_api_dict()

    @app.get("/api/update-check")
    async def api_update_check() -> dict:
        from route53_ddns import __version__ as app_version_str

        base = {"app_version": app_version_str}
        if not settings.github_repository:
            return {
                **base,
                "github_repository_configured": False,
                "update_available": False,
            }

        if http_client is None:
            return {
                **base,
                "github_repository_configured": True,
                "update_available": False,
                "error": "Service not ready",
            }

        owner, repo = split_github_repository(settings.github_repository)

        async with update_check_runtime.lock:
            now = time.monotonic()
            if (
                update_check_runtime.cached_payload is not None
                and (now - update_check_runtime.cached_at_monotonic)
                < update_check_runtime.ttl_seconds
            ):
                return update_check_runtime.cached_payload

            try:
                raw_tag, release_url = await fetch_latest_release(
                    http_client,
                    settings.github_api_base,
                    owner,
                    repo,
                )
                latest_norm = normalize_version_tag(raw_tag)
                update_available = is_remote_newer(raw_tag, app_version_str)
                payload = {
                    **base,
                    "github_repository_configured": True,
                    "latest_version": latest_norm,
                    "release_url": release_url,
                    "update_available": update_available,
                }
            except httpx.HTTPStatusError as e:
                logger.warning("GitHub API HTTP error: %s", e)
                payload = {
                    **base,
                    "github_repository_configured": True,
                    "update_available": False,
                    "error": f"GitHub API error: {e.response.status_code}",
                }
            except Exception as e:  # noqa: BLE001
                logger.warning("GitHub API request failed: %s", e, exc_info=True)
                payload = {
                    **base,
                    "github_repository_configured": True,
                    "update_available": False,
                    "error": str(e),
                }

            update_check_runtime.cached_payload = payload
            update_check_runtime.cached_at_monotonic = time.monotonic()
            return payload

    @app.post("/records/{index}/update")
    async def trigger_update(index: int) -> RedirectResponse:
        if http_client is None:
            raise HTTPException(503, "Service not ready")
        try:
            await manual_update_index(
                http_client,
                state,
                file_config.checkip_url,
                index,
            )
        except IndexError as e:
            raise HTTPException(404, str(e)) from e
        return RedirectResponse(url="/", status_code=303)

    @app.post("/records/update-all")
    async def trigger_update_all() -> RedirectResponse:
        if http_client is None:
            raise HTTPException(503, "Service not ready")
        await manual_update_all(
            http_client,
            state,
            file_config.checkip_url,
        )
        return RedirectResponse(url="/", status_code=303)

    return app


def create_app() -> FastAPI:
    settings = get_settings()
    file_config = load_file_config(settings.resolved_config_path())
    return build_app(settings, file_config)


def run() -> None:
    setup_logging()
    clear_settings_cache()
    settings = get_settings()
    import uvicorn

    uvicorn.run(
        "route53_ddns.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_config=None,
    )
