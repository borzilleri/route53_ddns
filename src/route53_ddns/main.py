from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from route53_ddns.config import Settings, clear_settings_cache, get_settings
from route53_ddns.logging_config import setup_logging
from route53_ddns.poller import manual_update_index, poller_loop
from route53_ddns.route53_ops import verify_credentials
from route53_ddns.state import AppState, RecordRuntime

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def build_app(settings: Settings) -> FastAPI:
    records_cfg = settings.load_records()
    state = AppState(poll_interval_seconds=settings.poll_interval_seconds)
    for i, rc in enumerate(records_cfg):
        state.records.append(RecordRuntime(index=i, config=rc))

    stop_event: asyncio.Event | None = None
    poller_task: asyncio.Task | None = None
    http_client: httpx.AsyncClient | None = None

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
            poller_loop(http_client, settings, state, stop_event),
        )
        logger.info("Started poller (interval=%ss)", settings.poll_interval_seconds)
        yield
        if stop_event:
            stop_event.set()
        if poller_task:
            await poller_task
        if http_client:
            await http_client.aclose()
        logger.info("Shutdown complete")

    app = FastAPI(title="route53-ddns", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        async with state.lock:
            ctx = state.snapshot_for_template()
        return templates.TemplateResponse(request, "index.html", ctx)

    @app.post("/records/{index}/update")
    async def trigger_update(index: int) -> RedirectResponse:
        if http_client is None:
            raise HTTPException(503, "Service not ready")
        try:
            await manual_update_index(
                http_client,
                state,
                settings.checkip_url,
                index,
            )
        except IndexError as e:
            raise HTTPException(404, str(e)) from e
        return RedirectResponse(url="/", status_code=303)

    return app


def create_app() -> FastAPI:
    return build_app(get_settings())


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
