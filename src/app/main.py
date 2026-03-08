import logging
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeSerializer

from app.claude_client import ClaudeClient, AuthError
from app.config import ConfigManager
from app.scheduler import UsageScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "changeme")
FETCH_INTERVAL_MINUTES = int(os.environ.get("FETCH_INTERVAL_MINUTES", "15"))

# Load TRMNL Liquid template for display in setup instructions
_template_path = os.path.join(os.path.dirname(__file__), "trmnl-template.html")
try:
    with open(_template_path) as f:
        TRMNL_TEMPLATE = f.read()
except FileNotFoundError:
    TRMNL_TEMPLATE = ""

config = ConfigManager(data_dir=DATA_DIR)
usage_scheduler = UsageScheduler(data_dir=DATA_DIR)
serializer = URLSafeSerializer(WEB_PASSWORD)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from datetime import datetime, timedelta, timezone

    # Schedule the first run 30 seconds after startup, then every interval
    first_run = datetime.now(timezone.utc) + timedelta(seconds=30)
    scheduler.add_job(
        usage_scheduler.fetch_and_push,
        "interval",
        minutes=FETCH_INTERVAL_MINUTES,
        id="fetch_and_push",
        next_run_time=first_run,
    )
    scheduler.start()
    logger.info(f"Scheduler started: fetching every {FETCH_INTERVAL_MINUTES} min (first run in 30s)")
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)


def _is_authenticated(request: Request) -> bool:
    token = request.cookies.get("session")
    if not token:
        return False
    try:
        serializer.loads(token)
        return True
    except Exception:
        return False


def _base_context(request: Request, cfg: dict, **overrides) -> dict:
    ctx = {
        "request": request,
        "has_credentials": config.has_credentials(),
        "last_fetch": cfg.get("last_fetch"),
        "last_push": cfg.get("last_push"),
        "last_error": cfg.get("last_error"),
        "last_usage": cfg.get("last_usage"),
        "session_key": cfg.get("session_key", ""),
        "org_id": cfg.get("org_id", ""),
        "orgs": None,
        "saved": False,
        "config_error": None,
        "webhook_url": cfg.get("webhook_url", ""),
        "trmnl_template": TRMNL_TEMPLATE,
    }
    ctx.update(overrides)
    return ctx


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not _is_authenticated(request):
        return templates.TemplateResponse("login.html", {"request": request, "error": None})

    cfg = config.load()
    return templates.TemplateResponse("index.html", _base_context(request, cfg))


@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    if password != WEB_PASSWORD:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid password"},
            status_code=401,
        )
    response = RedirectResponse(url="/", status_code=303)
    token = serializer.dumps("authenticated")
    response.set_cookie("session", token, httponly=True, max_age=86400 * 7)
    return response


@app.post("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session")
    return response


@app.post("/config/session-key")
async def fetch_orgs(request: Request, session_key: str = Form(...)):
    if not _is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)

    session_key = session_key.strip()
    try:
        client = ClaudeClient(session_key)
        orgs = await client.fetch_organizations()
    except AuthError:
        cfg = config.load()
        return templates.TemplateResponse("index.html", _base_context(request, cfg,
            session_key=session_key,
            config_error="Invalid or expired session key. Please copy a fresh sessionKey cookie from claude.ai.",
        ))
    except Exception as e:
        cfg = config.load()
        return templates.TemplateResponse("index.html", _base_context(request, cfg,
            session_key=session_key,
            config_error=f"Error fetching orgs: {e}",
        ))

    cfg = config.load()
    return templates.TemplateResponse("index.html", _base_context(request, cfg,
        session_key=session_key,
        orgs=[{"uuid": o.uuid, "name": o.display_name} for o in orgs],
    ))


@app.post("/config")
async def save_config(request: Request, session_key: str = Form(...), org_id: str = Form(...)):
    if not _is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)

    config.save_credentials(session_key.strip(), org_id.strip())
    await usage_scheduler.fetch_and_push()

    cfg = config.load()
    return templates.TemplateResponse("index.html", _base_context(request, cfg, saved=True))


@app.post("/config/webhook")
async def save_webhook(request: Request, webhook_url: str = Form(...)):
    if not _is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)
    config.save_webhook_url(webhook_url.strip())
    return RedirectResponse(url="/", status_code=303)


@app.post("/fetch")
async def manual_fetch(request: Request):
    if not _is_authenticated(request):
        # Allow unauthenticated calls from localhost/private IPs
        client_ip = request.client.host if request.client else ""
        if client_ip not in ("127.0.0.1", "::1") and not client_ip.startswith(("192.168.", "10.", "172.")):
            return RedirectResponse(url="/", status_code=303)
    await usage_scheduler.fetch_and_push()
    return RedirectResponse(url="/", status_code=303)
