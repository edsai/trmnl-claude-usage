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
WEBHOOK_UUID = os.environ.get("TRMNL_WEBHOOK_UUID", "")
WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "changeme")
FETCH_INTERVAL_MINUTES = int(os.environ.get("FETCH_INTERVAL_MINUTES", "30"))

config = ConfigManager(data_dir=DATA_DIR)
usage_scheduler = UsageScheduler(webhook_uuid=WEBHOOK_UUID, data_dir=DATA_DIR)
serializer = URLSafeSerializer(WEB_PASSWORD)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        usage_scheduler.fetch_and_push,
        "interval",
        minutes=FETCH_INTERVAL_MINUTES,
        id="fetch_and_push",
        next_run_time=None,
    )
    scheduler.start()
    logger.info(f"Scheduler started: fetching every {FETCH_INTERVAL_MINUTES} min")
    import asyncio
    asyncio.get_event_loop().call_later(5, lambda: asyncio.ensure_future(usage_scheduler.fetch_and_push()))
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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not _is_authenticated(request):
        return templates.TemplateResponse("login.html", {"request": request, "error": None})

    cfg = config.load()
    return templates.TemplateResponse("index.html", {
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
    })


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
        return templates.TemplateResponse("index.html", {
            "request": request,
            "has_credentials": config.has_credentials(),
            "last_fetch": cfg.get("last_fetch"),
            "last_push": cfg.get("last_push"),
            "last_error": "Invalid or expired session key",
            "last_usage": cfg.get("last_usage"),
            "session_key": session_key,
            "org_id": cfg.get("org_id", ""),
            "orgs": None,
            "saved": False,
        })
    except Exception as e:
        cfg = config.load()
        return templates.TemplateResponse("index.html", {
            "request": request,
            "has_credentials": config.has_credentials(),
            "last_fetch": cfg.get("last_fetch"),
            "last_push": cfg.get("last_push"),
            "last_error": f"Error fetching orgs: {e}",
            "last_usage": cfg.get("last_usage"),
            "session_key": session_key,
            "org_id": cfg.get("org_id", ""),
            "orgs": None,
            "saved": False,
        })

    cfg = config.load()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "has_credentials": config.has_credentials(),
        "last_fetch": cfg.get("last_fetch"),
        "last_push": cfg.get("last_push"),
        "last_error": cfg.get("last_error"),
        "last_usage": cfg.get("last_usage"),
        "session_key": session_key,
        "org_id": cfg.get("org_id", ""),
        "orgs": [{"uuid": o.uuid, "name": o.display_name} for o in orgs],
        "saved": False,
    })


@app.post("/config")
async def save_config(request: Request, session_key: str = Form(...), org_id: str = Form(...)):
    if not _is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)

    config.save_credentials(session_key.strip(), org_id.strip())
    await usage_scheduler.fetch_and_push()

    cfg = config.load()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "has_credentials": config.has_credentials(),
        "last_fetch": cfg.get("last_fetch"),
        "last_push": cfg.get("last_push"),
        "last_error": cfg.get("last_error"),
        "last_usage": cfg.get("last_usage"),
        "session_key": cfg.get("session_key", ""),
        "org_id": cfg.get("org_id", ""),
        "orgs": None,
        "saved": True,
    })


@app.post("/fetch")
async def manual_fetch(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)
    await usage_scheduler.fetch_and_push()
    return RedirectResponse(url="/", status_code=303)
