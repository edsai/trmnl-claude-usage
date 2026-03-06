# TRMNL Claude Usage Dashboard - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Docker container that fetches Claude usage data, computes projections, and pushes stats to a TRMNL e-ink dashboard, with a password-protected web UI for config.

**Architecture:** Python FastAPI app with APScheduler background job. Fetches from `claude.ai/api/organizations/{org_id}/usage` every 30 min, computes daily projections, POSTs merge_variables to TRMNL webhook. Web UI on port 8085 for session key management.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, APScheduler, httpx, Jinja2

**Design Doc:** `docs/plans/2026-03-06-trmnl-claude-usage-design.md`

---

### Task 1: Project Scaffolding

**Files:**
- Create: `src/requirements.txt`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `src/app/__init__.py`

**Step 1: Create requirements.txt**

Create `src/requirements.txt`:

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
httpx==0.28.1
apscheduler==3.11.0
jinja2==3.1.5
python-multipart==0.0.20
itsdangerous==2.2.0
```

**Step 2: Create Dockerfile**

Create `Dockerfile`:

```dockerfile
FROM python:3.12-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8085

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8085"]
```

**Step 3: Create docker-compose.yml**

Create `docker-compose.yml`:

```yaml
services:
  trmnl-claude:
    container_name: trmnl-claude
    build:
      context: /var/docker/trmnl-claude/src
      dockerfile: /home/esaipetch/dockerfiles-mserver/trmnl-claude/Dockerfile
    restart: unless-stopped
    env_file:
      - /var/docker/trmnl-claude/.env
    ports:
      - 8085:8085
    volumes:
      - /var/docker/trmnl-claude/data:/app/data
    networks:
      - npm-network

networks:
  npm-network:
    external: true
```

**Step 4: Create .env.example**

Create `.env.example`:

```
TRMNL_WEBHOOK_UUID=your-webhook-uuid-from-trmnl
WEB_PASSWORD=your-secure-password
```

**Step 5: Create app package init**

Create `src/app/__init__.py` (empty file).

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding with Dockerfile, compose, and requirements"
```

---

### Task 2: Config Module

**Files:**
- Create: `src/app/config.py`
- Create: `src/tests/test_config.py`

**Step 1: Write the failing test**

Create `src/tests/__init__.py` (empty) and `src/tests/test_config.py`:

```python
import json
import os
import tempfile
import pytest
from pathlib import Path


def test_config_loads_defaults_when_no_file():
    from app.config import ConfigManager
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ConfigManager(data_dir=tmpdir)
        cfg = mgr.load()
        assert cfg["session_key"] is None
        assert cfg["org_id"] is None
        assert cfg["last_fetch"] is None
        assert cfg["last_push"] is None


def test_config_saves_and_loads_session_key():
    from app.config import ConfigManager
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ConfigManager(data_dir=tmpdir)
        mgr.save_credentials("sk-test-123", "org-abc")
        cfg = mgr.load()
        assert cfg["session_key"] == "sk-test-123"
        assert cfg["org_id"] == "org-abc"


def test_config_updates_timestamps():
    from app.config import ConfigManager
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ConfigManager(data_dir=tmpdir)
        mgr.update_fetch_time()
        cfg = mgr.load()
        assert cfg["last_fetch"] is not None


def test_config_updates_push_time():
    from app.config import ConfigManager
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ConfigManager(data_dir=tmpdir)
        mgr.update_push_time()
        cfg = mgr.load()
        assert cfg["last_push"] is not None


def test_config_stores_last_usage():
    from app.config import ConfigManager
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ConfigManager(data_dir=tmpdir)
        usage = {"session_pct": 42, "opus_weekly_pct": 10}
        mgr.save_last_usage(usage)
        cfg = mgr.load()
        assert cfg["last_usage"]["session_pct"] == 42


def test_config_has_credentials():
    from app.config import ConfigManager
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ConfigManager(data_dir=tmpdir)
        assert mgr.has_credentials() is False
        mgr.save_credentials("key", "org")
        assert mgr.has_credentials() is True
```

**Step 2: Run test to verify it fails**

Run: `cd src && python -m pytest tests/test_config.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

Create `src/app/config.py`:

```python
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ConfigManager:
    def __init__(self, data_dir: str = "/app/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.data_dir / "config.json"

    def load(self) -> dict[str, Any]:
        if self.config_path.exists():
            with open(self.config_path) as f:
                return json.load(f)
        return self._defaults()

    def _defaults(self) -> dict[str, Any]:
        return {
            "session_key": None,
            "org_id": None,
            "last_fetch": None,
            "last_push": None,
            "last_usage": None,
            "last_error": None,
        }

    def _save(self, cfg: dict[str, Any]) -> None:
        with open(self.config_path, "w") as f:
            json.dump(cfg, f, indent=2)

    def save_credentials(self, session_key: str, org_id: str) -> None:
        cfg = self.load()
        cfg["session_key"] = session_key
        cfg["org_id"] = org_id
        self._save(cfg)

    def has_credentials(self) -> bool:
        cfg = self.load()
        return bool(cfg.get("session_key")) and bool(cfg.get("org_id"))

    def update_fetch_time(self) -> None:
        cfg = self.load()
        cfg["last_fetch"] = datetime.now(timezone.utc).isoformat()
        self._save(cfg)

    def update_push_time(self) -> None:
        cfg = self.load()
        cfg["last_push"] = datetime.now(timezone.utc).isoformat()
        self._save(cfg)

    def save_last_usage(self, usage: dict[str, Any]) -> None:
        cfg = self.load()
        cfg["last_usage"] = usage
        self._save(cfg)

    def save_last_error(self, error: str | None) -> None:
        cfg = self.load()
        cfg["last_error"] = error
        self._save(cfg)
```

**Step 4: Run test to verify it passes**

Run: `cd src && python -m pytest tests/test_config.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add src/app/config.py src/tests/
git commit -m "feat: config manager with persistent JSON storage"
```

---

### Task 3: Claude API Client

**Files:**
- Create: `src/app/claude_client.py`
- Create: `src/tests/test_claude_client.py`

The Claude API response from `GET /api/organizations/{org_id}/usage` looks like:

```json
{
  "five_hour": {"utilization": 67, "resets_at": "2026-03-06T19:45:00.000Z"},
  "seven_day": {"utilization": 35, "resets_at": "2026-03-10T17:59:00.000Z"},
  "seven_day_opus": {"utilization": 42},
  "seven_day_sonnet": {"utilization": 28, "resets_at": "2026-03-10T17:59:00.000Z"}
}
```

**Step 1: Write the failing test**

Create `src/tests/test_claude_client.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.claude_client import ClaudeClient, UsageData


MOCK_RESPONSE = {
    "five_hour": {"utilization": 67, "resets_at": "2026-03-06T19:45:00.000Z"},
    "seven_day": {"utilization": 35, "resets_at": "2026-03-10T17:59:00.000Z"},
    "seven_day_opus": {"utilization": 42},
    "seven_day_sonnet": {"utilization": 28, "resets_at": "2026-03-10T17:59:00.000Z"},
}


def test_parse_usage_response():
    usage = ClaudeClient.parse_response(MOCK_RESPONSE)
    assert usage.session_pct == 67
    assert usage.weekly_pct == 35
    assert usage.opus_weekly_pct == 42
    assert usage.sonnet_weekly_pct == 28
    assert usage.session_reset is not None
    assert usage.weekly_reset is not None


def test_parse_usage_handles_missing_fields():
    usage = ClaudeClient.parse_response({})
    assert usage.session_pct == 0
    assert usage.weekly_pct == 0
    assert usage.opus_weekly_pct == 0
    assert usage.sonnet_weekly_pct == 0


def test_parse_utilization_as_float():
    data = {"five_hour": {"utilization": 42.5}}
    usage = ClaudeClient.parse_response(data)
    assert usage.session_pct == 42.5


def test_parse_utilization_as_string():
    data = {"five_hour": {"utilization": "55"}}
    usage = ClaudeClient.parse_response(data)
    assert usage.session_pct == 55.0


def test_usage_data_to_dict():
    usage = ClaudeClient.parse_response(MOCK_RESPONSE)
    d = usage.to_dict()
    assert d["session_pct"] == 67
    assert d["opus_weekly_pct"] == 42
    assert "session_reset" in d
```

**Step 2: Run test to verify it fails**

Run: `cd src && python -m pytest tests/test_claude_client.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

Create `src/app/claude_client.py`:

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx


@dataclass
class UsageData:
    session_pct: float = 0.0
    session_reset: datetime | None = None
    weekly_pct: float = 0.0
    weekly_reset: datetime | None = None
    opus_weekly_pct: float = 0.0
    sonnet_weekly_pct: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_pct": self.session_pct,
            "session_reset": self.session_reset.isoformat() if self.session_reset else None,
            "weekly_pct": self.weekly_pct,
            "weekly_reset": self.weekly_reset.isoformat() if self.weekly_reset else None,
            "opus_weekly_pct": self.opus_weekly_pct,
            "sonnet_weekly_pct": self.sonnet_weekly_pct,
        }


class ClaudeClient:
    BASE_URL = "https://claude.ai/api"

    def __init__(self, session_key: str, org_id: str):
        self.session_key = session_key
        self.org_id = org_id

    async def fetch_usage(self) -> UsageData:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/organizations/{self.org_id}/usage",
                headers={
                    "Accept": "application/json",
                    "Cookie": f"sessionKey={self.session_key}",
                },
                timeout=30.0,
            )
            if resp.status_code in (401, 403):
                raise AuthError("Session key expired or unauthorized")
            resp.raise_for_status()
            return self.parse_response(resp.json())

    @staticmethod
    def parse_response(data: dict[str, Any]) -> UsageData:
        usage = UsageData()

        five_hour = data.get("five_hour", {})
        usage.session_pct = _parse_utilization(five_hour.get("utilization", 0))
        usage.session_reset = _parse_iso_date(five_hour.get("resets_at"))

        seven_day = data.get("seven_day", {})
        usage.weekly_pct = _parse_utilization(seven_day.get("utilization", 0))
        usage.weekly_reset = _parse_iso_date(seven_day.get("resets_at"))

        opus = data.get("seven_day_opus", {})
        usage.opus_weekly_pct = _parse_utilization(opus.get("utilization", 0))

        sonnet = data.get("seven_day_sonnet", {})
        usage.sonnet_weekly_pct = _parse_utilization(sonnet.get("utilization", 0))

        return usage


class AuthError(Exception):
    pass


def _parse_utilization(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _parse_iso_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
```

**Step 4: Run test to verify it passes**

Run: `cd src && python -m pytest tests/test_claude_client.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add src/app/claude_client.py src/tests/test_claude_client.py
git commit -m "feat: Claude API client with usage response parsing"
```

---

### Task 4: Projection Engine

**Files:**
- Create: `src/app/projection.py`
- Create: `src/tests/test_projection.py`

Port of `DailyConsumptionTracker.swift` logic.

**Step 1: Write the failing test**

Create `src/tests/test_projection.py`:

```python
import json
import tempfile
from datetime import datetime, timedelta, timezone
from app.projection import ProjectionEngine, DailySnapshot


def _engine(tmpdir: str) -> ProjectionEngine:
    return ProjectionEngine(data_dir=tmpdir)


def test_record_snapshot_creates_entry():
    with tempfile.TemporaryDirectory() as tmpdir:
        eng = _engine(tmpdir)
        eng.record_if_needed(weekly_pct=25.0)
        snaps = eng.load_snapshots()
        assert len(snaps) == 1
        assert snaps[0]["weekly_pct"] == 25.0


def test_record_snapshot_idempotent_same_day():
    with tempfile.TemporaryDirectory() as tmpdir:
        eng = _engine(tmpdir)
        eng.record_if_needed(weekly_pct=25.0)
        eng.record_if_needed(weekly_pct=30.0)
        snaps = eng.load_snapshots()
        assert len(snaps) == 1


def test_detects_weekly_reset():
    with tempfile.TemporaryDirectory() as tmpdir:
        eng = _engine(tmpdir)
        # Simulate existing snapshot with high usage
        snap = DailySnapshot(
            date=(datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat(),
            weekly_pct=80.0,
            day_of_week=3,
        )
        eng.save_snapshots([snap.to_dict()])
        # Now current % is much lower -> reset detected
        eng.record_if_needed(weekly_pct=5.0)
        snaps = eng.load_snapshots()
        # Old snapshot should be cleared, new one recorded
        assert len(snaps) == 1
        assert snaps[0]["weekly_pct"] == 5.0


def test_average_daily_pace():
    with tempfile.TemporaryDirectory() as tmpdir:
        eng = _engine(tmpdir)
        # Plant a snapshot from 2 days ago
        two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
        eng.save_snapshots([{
            "date": two_days_ago,
            "weekly_pct": 10.0,
            "day_of_week": 1,
        }])
        pace = eng.average_daily_pace(current_pct=30.0)
        # (30 - 10) / 2 = 10%/day
        assert 9.0 <= pace <= 11.0


def test_projected_at_reset():
    with tempfile.TemporaryDirectory() as tmpdir:
        eng = _engine(tmpdir)
        two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
        eng.save_snapshots([{
            "date": two_days_ago,
            "weekly_pct": 10.0,
            "day_of_week": 1,
        }])
        reset_time = datetime.now(timezone.utc) + timedelta(days=3)
        projected = eng.projected_at_reset(current_pct=30.0, reset_time=reset_time)
        # pace ~10/day, 3 days remaining: 30 + 30 = 60
        assert 55.0 <= projected <= 65.0


def test_projected_capped_at_100():
    with tempfile.TemporaryDirectory() as tmpdir:
        eng = _engine(tmpdir)
        two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
        eng.save_snapshots([{
            "date": two_days_ago,
            "weekly_pct": 10.0,
            "day_of_week": 1,
        }])
        reset_time = datetime.now(timezone.utc) + timedelta(days=10)
        projected = eng.projected_at_reset(current_pct=80.0, reset_time=reset_time)
        assert projected == 100.0


def test_today_consumption():
    with tempfile.TemporaryDirectory() as tmpdir:
        eng = _engine(tmpdir)
        today = datetime.now(timezone.utc).date().isoformat()
        eng.save_snapshots([{
            "date": today,
            "weekly_pct": 20.0,
            "day_of_week": 4,
        }])
        consumed = eng.today_consumption(current_pct=28.0)
        assert consumed == 8.0


def test_remaining_budget_per_day():
    with tempfile.TemporaryDirectory() as tmpdir:
        eng = _engine(tmpdir)
        reset_time = datetime.now(timezone.utc) + timedelta(days=4)
        budget = eng.remaining_budget_per_day(current_pct=60.0, reset_time=reset_time)
        # (100 - 60) / 4 = 10
        assert 9.5 <= budget <= 10.5


def test_compute_projections_returns_dict():
    with tempfile.TemporaryDirectory() as tmpdir:
        eng = _engine(tmpdir)
        reset_time = datetime.now(timezone.utc) + timedelta(days=5)
        result = eng.compute_projections(current_pct=40.0, reset_time=reset_time)
        assert "projected_at_reset" in result
        assert "today_usage" in result
        assert "avg_daily_pace" in result
        assert "budget_per_day" in result
```

**Step 2: Run test to verify it fails**

Run: `cd src && python -m pytest tests/test_projection.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

Create `src/app/projection.py`:

```python
import json
from dataclasses import dataclass
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
from typing import Any


@dataclass
class DailySnapshot:
    date: str  # ISO date string YYYY-MM-DD
    weekly_pct: float
    day_of_week: int  # 1=Mon ... 7=Sun

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "weekly_pct": self.weekly_pct,
            "day_of_week": self.day_of_week,
        }


class ProjectionEngine:
    MAX_SNAPSHOTS = 8

    def __init__(self, data_dir: str = "/app/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_path = self.data_dir / "snapshots.json"

    def load_snapshots(self) -> list[dict[str, Any]]:
        if self.snapshot_path.exists():
            with open(self.snapshot_path) as f:
                return json.load(f)
        return []

    def save_snapshots(self, snapshots: list[dict[str, Any]]) -> None:
        with open(self.snapshot_path, "w") as f:
            json.dump(snapshots, f, indent=2)

    def record_if_needed(self, weekly_pct: float) -> None:
        snapshots = self.load_snapshots()
        now = datetime.now(timezone.utc)
        today_str = now.date().isoformat()

        # Detect weekly reset: % dropped by more than 5 points
        if snapshots:
            last_pct = snapshots[-1]["weekly_pct"]
            if weekly_pct < last_pct - 5.0:
                snapshots.clear()

        # Already recorded today
        if snapshots and snapshots[-1]["date"] == today_str:
            return

        snapshots.append({
            "date": today_str,
            "weekly_pct": weekly_pct,
            "day_of_week": now.isoweekday(),  # 1=Mon ... 7=Sun
        })

        # Keep at most MAX_SNAPSHOTS
        if len(snapshots) > self.MAX_SNAPSHOTS:
            snapshots = snapshots[-self.MAX_SNAPSHOTS:]

        self.save_snapshots(snapshots)

    def average_daily_pace(self, current_pct: float) -> float:
        snapshots = self.load_snapshots()
        if not snapshots:
            return 0.0

        first = snapshots[0]
        first_date = date.fromisoformat(first["date"])
        now = datetime.now(timezone.utc)
        elapsed_days = max(0.01, (now.date() - first_date).total_seconds() / 86400.0)

        total_consumed = max(0.0, current_pct - first["weekly_pct"])
        return total_consumed / elapsed_days

    def projected_at_reset(self, current_pct: float, reset_time: datetime | None) -> float:
        if reset_time is None:
            return current_pct

        now = datetime.now(timezone.utc)
        if reset_time <= now:
            return current_pct

        pace = self.average_daily_pace(current_pct)
        remaining_days = (reset_time - now).total_seconds() / 86400.0
        projected = current_pct + remaining_days * pace
        return min(projected, 100.0)

    def today_consumption(self, current_pct: float) -> float:
        snapshots = self.load_snapshots()
        today_str = datetime.now(timezone.utc).date().isoformat()

        if snapshots and snapshots[-1]["date"] == today_str:
            return max(0.0, current_pct - snapshots[-1]["weekly_pct"])
        return 0.0

    def remaining_budget_per_day(self, current_pct: float, reset_time: datetime | None) -> float:
        remaining = max(0.0, 100.0 - current_pct)
        if reset_time is None:
            return remaining

        now = datetime.now(timezone.utc)
        if reset_time <= now:
            return remaining

        days_remaining = max(0.1, (reset_time - now).total_seconds() / 86400.0)
        return remaining / days_remaining

    def compute_projections(self, current_pct: float, reset_time: datetime | None) -> dict[str, float]:
        return {
            "projected_at_reset": round(self.projected_at_reset(current_pct, reset_time), 1),
            "today_usage": round(self.today_consumption(current_pct), 1),
            "avg_daily_pace": round(self.average_daily_pace(current_pct), 1),
            "budget_per_day": round(self.remaining_budget_per_day(current_pct, reset_time), 1),
        }
```

**Step 4: Run test to verify it passes**

Run: `cd src && python -m pytest tests/test_projection.py -v`
Expected: All 9 tests PASS

**Step 5: Commit**

```bash
git add src/app/projection.py src/tests/test_projection.py
git commit -m "feat: projection engine with daily snapshots and pace calculations"
```

---

### Task 5: TRMNL Client

**Files:**
- Create: `src/app/trmnl_client.py`
- Create: `src/tests/test_trmnl_client.py`

**Step 1: Write the failing test**

Create `src/tests/test_trmnl_client.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.trmnl_client import TRMNLClient


def test_build_healthy_payload():
    client = TRMNLClient(webhook_uuid="test-uuid")
    usage = {
        "session_pct": 67,
        "session_reset": "2:45 PM",
        "opus_weekly_pct": 42,
        "sonnet_weekly_pct": 28,
    }
    projections = {
        "projected_at_reset": 71.0,
        "today_usage": 8.0,
        "avg_daily_pace": 12.0,
        "budget_per_day": 9.6,
    }
    payload = client.build_payload("healthy", usage, projections)
    mv = payload["merge_variables"]
    assert mv["status"] == "healthy"
    assert mv["session_pct"] == 67
    assert mv["projected_at_reset"] == 71.0
    assert "config_url" not in mv or mv["config_url"]


def test_build_expired_payload():
    client = TRMNLClient(webhook_uuid="test-uuid")
    payload = client.build_payload(
        "expired", {}, {},
        error_message="Session Key Expired",
        last_valid="Mar 5, 2:30 PM",
    )
    mv = payload["merge_variables"]
    assert mv["status"] == "expired"
    assert mv["error_message"] == "Session Key Expired"
    assert mv["last_valid"] == "Mar 5, 2:30 PM"


def test_build_setup_payload():
    client = TRMNLClient(webhook_uuid="test-uuid")
    payload = client.build_payload("setup_required", {}, {})
    mv = payload["merge_variables"]
    assert mv["status"] == "setup_required"


def test_webhook_url():
    client = TRMNLClient(webhook_uuid="abc-123")
    assert client.webhook_url == "https://trmnl.com/api/custom_plugins/abc-123"
```

**Step 2: Run test to verify it fails**

Run: `cd src && python -m pytest tests/test_trmnl_client.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

Create `src/app/trmnl_client.py`:

```python
from datetime import datetime, timezone
from typing import Any

import httpx


class TRMNLClient:
    BASE_URL = "https://trmnl.com/api/custom_plugins"

    def __init__(self, webhook_uuid: str, config_url: str = "http://192.168.200.7:8085"):
        self.webhook_uuid = webhook_uuid
        self.config_url = config_url

    @property
    def webhook_url(self) -> str:
        return f"{self.BASE_URL}/{self.webhook_uuid}"

    def build_payload(
        self,
        status: str,
        usage: dict[str, Any],
        projections: dict[str, Any],
        error_message: str | None = None,
        last_valid: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "merge_variables": {
                "status": status,
                "session_pct": usage.get("session_pct", 0),
                "session_reset": usage.get("session_reset", ""),
                "opus_weekly_pct": usage.get("opus_weekly_pct", 0),
                "sonnet_weekly_pct": usage.get("sonnet_weekly_pct", 0),
                "projected_at_reset": projections.get("projected_at_reset", 0),
                "today_usage": projections.get("today_usage", 0),
                "avg_daily_pace": projections.get("avg_daily_pace", 0),
                "budget_per_day": projections.get("budget_per_day", 0),
                "updated_at": now.strftime("%-I:%M %p"),
                "error_message": error_message,
                "config_url": self.config_url,
                "last_valid": last_valid,
            }
        }

    async def push(self, payload: dict[str, Any]) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )
            return resp.status_code == 200
```

**Step 4: Run test to verify it passes**

Run: `cd src && python -m pytest tests/test_trmnl_client.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add src/app/trmnl_client.py src/tests/test_trmnl_client.py
git commit -m "feat: TRMNL webhook client with payload builder"
```

---

### Task 6: Scheduler / Orchestrator

**Files:**
- Create: `src/app/scheduler.py`
- Create: `src/tests/test_scheduler.py`

This is the core loop: fetch -> project -> push.

**Step 1: Write the failing test**

Create `src/tests/test_scheduler.py`:

```python
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from app.scheduler import UsageScheduler


@pytest.fixture
def scheduler():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = UsageScheduler(
            webhook_uuid="test-uuid",
            data_dir=tmpdir,
        )
        yield s


@pytest.mark.asyncio
async def test_fetch_and_push_healthy(scheduler):
    mock_usage_data = MagicMock()
    mock_usage_data.session_pct = 67.0
    mock_usage_data.weekly_pct = 35.0
    mock_usage_data.opus_weekly_pct = 42.0
    mock_usage_data.sonnet_weekly_pct = 28.0
    mock_usage_data.session_reset = datetime.now(timezone.utc) + timedelta(hours=3)
    mock_usage_data.weekly_reset = datetime.now(timezone.utc) + timedelta(days=5)
    mock_usage_data.to_dict.return_value = {
        "session_pct": 67.0,
        "opus_weekly_pct": 42.0,
        "sonnet_weekly_pct": 28.0,
    }

    scheduler.config.save_credentials("sk-test", "org-test")

    with patch("app.scheduler.ClaudeClient") as MockClient:
        instance = MockClient.return_value
        instance.fetch_usage = AsyncMock(return_value=mock_usage_data)

        with patch.object(scheduler.trmnl, "push", new_callable=AsyncMock, return_value=True):
            await scheduler.fetch_and_push()

    cfg = scheduler.config.load()
    assert cfg["last_fetch"] is not None
    assert cfg["last_push"] is not None
    assert cfg["last_error"] is None


@pytest.mark.asyncio
async def test_fetch_and_push_no_credentials(scheduler):
    await scheduler.fetch_and_push()
    # Should push setup_required status
    # No crash expected


@pytest.mark.asyncio
async def test_fetch_and_push_auth_error(scheduler):
    from app.claude_client import AuthError
    scheduler.config.save_credentials("sk-expired", "org-test")

    with patch("app.scheduler.ClaudeClient") as MockClient:
        instance = MockClient.return_value
        instance.fetch_usage = AsyncMock(side_effect=AuthError("expired"))

        with patch.object(scheduler.trmnl, "push", new_callable=AsyncMock, return_value=True):
            await scheduler.fetch_and_push()

    cfg = scheduler.config.load()
    assert cfg["last_error"] is not None
```

**Step 2: Run test to verify it fails**

Run: `cd src && python -m pytest tests/test_scheduler.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

Create `src/app/scheduler.py`:

```python
import logging
from datetime import datetime, timezone
from typing import Any

from app.claude_client import ClaudeClient, AuthError, UsageData
from app.config import ConfigManager
from app.projection import ProjectionEngine
from app.trmnl_client import TRMNLClient

logger = logging.getLogger(__name__)


class UsageScheduler:
    def __init__(self, webhook_uuid: str, data_dir: str = "/app/data"):
        self.config = ConfigManager(data_dir=data_dir)
        self.projection = ProjectionEngine(data_dir=data_dir)
        self.trmnl = TRMNLClient(webhook_uuid=webhook_uuid)

    async def fetch_and_push(self) -> None:
        cfg = self.config.load()

        if not self.config.has_credentials():
            logger.info("No credentials configured, pushing setup_required")
            payload = self.trmnl.build_payload("setup_required", {}, {})
            try:
                await self.trmnl.push(payload)
            except Exception as e:
                logger.error(f"Failed to push setup_required: {e}")
            return

        session_key = cfg["session_key"]
        org_id = cfg["org_id"]

        try:
            client = ClaudeClient(session_key, org_id)
            usage = await client.fetch_usage()
            self.config.update_fetch_time()
            self.config.save_last_error(None)

            # Record snapshot for projections
            self.projection.record_if_needed(usage.weekly_pct)

            # Format reset time for display
            session_reset_str = _format_time(usage.session_reset)

            # Compute projections
            projections = self.projection.compute_projections(
                current_pct=usage.weekly_pct,
                reset_time=usage.weekly_reset,
            )

            usage_dict = {
                "session_pct": usage.session_pct,
                "session_reset": session_reset_str,
                "opus_weekly_pct": usage.opus_weekly_pct,
                "sonnet_weekly_pct": usage.sonnet_weekly_pct,
            }

            self.config.save_last_usage(usage_dict | projections)

            payload = self.trmnl.build_payload("healthy", usage_dict, projections)
            pushed = await self.trmnl.push(payload)
            if pushed:
                self.config.update_push_time()
                logger.info(f"Pushed usage: session={usage.session_pct}%, weekly={usage.weekly_pct}%")
            else:
                logger.warning("TRMNL push returned non-200")

        except AuthError as e:
            logger.warning(f"Auth error: {e}")
            self.config.save_last_error(str(e))
            last_usage = cfg.get("last_usage", {})
            last_fetch = cfg.get("last_fetch")
            last_valid = _format_datetime(last_fetch) if last_fetch else None
            payload = self.trmnl.build_payload(
                "expired", {}, {},
                error_message="Session Key Expired",
                last_valid=last_valid,
            )
            try:
                await self.trmnl.push(payload)
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Fetch error: {e}")
            self.config.save_last_error(str(e))


def _format_time(dt: datetime | None) -> str:
    if dt is None:
        return ""
    local = dt.astimezone()
    return local.strftime("%-I:%M %p")


def _format_datetime(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        local = dt.astimezone()
        return local.strftime("%b %-d, %-I:%M %p")
    except (ValueError, AttributeError):
        return iso_str
```

**Step 4: Run test to verify it passes**

Run: `cd src && python -m pytest tests/test_scheduler.py -v`
Expected: All 3 tests PASS

Note: You'll need `pytest-asyncio` — add it to a `src/requirements-dev.txt`:
```
pytest==8.3.4
pytest-asyncio==0.24.0
```

**Step 5: Commit**

```bash
git add src/app/scheduler.py src/tests/test_scheduler.py src/requirements-dev.txt
git commit -m "feat: scheduler orchestrating fetch -> project -> push loop"
```

---

### Task 7: Web UI

**Files:**
- Create: `src/app/main.py`
- Create: `src/app/templates/index.html`
- Create: `src/app/templates/login.html`

**Step 1: Create login template**

Create `src/app/templates/login.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>TRMNL Claude Usage - Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 400px; margin: 80px auto; padding: 0 20px; background: #1a1a2e; color: #e0e0e0; }
        h1 { color: #d4a574; font-size: 1.4em; }
        input[type=password] { width: 100%; padding: 10px; margin: 10px 0; box-sizing: border-box; background: #16213e; border: 1px solid #0f3460; color: #e0e0e0; border-radius: 4px; }
        button { background: #d4a574; color: #1a1a2e; border: none; padding: 10px 24px; cursor: pointer; border-radius: 4px; font-weight: bold; }
        .error { color: #e74c3c; margin-top: 10px; }
    </style>
</head>
<body>
    <h1>TRMNL Claude Usage</h1>
    <form method="post" action="/login">
        <input type="password" name="password" placeholder="Password" required autofocus>
        <button type="submit">Login</button>
    </form>
    {% if error %}
    <p class="error">{{ error }}</p>
    {% endif %}
</body>
</html>
```

**Step 2: Create main dashboard template**

Create `src/app/templates/index.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>TRMNL Claude Usage</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 600px; margin: 20px auto; padding: 0 20px; background: #1a1a2e; color: #e0e0e0; }
        h1 { color: #d4a574; font-size: 1.4em; }
        h2 { color: #d4a574; font-size: 1.1em; margin-top: 24px; }
        .card { background: #16213e; border: 1px solid #0f3460; border-radius: 8px; padding: 16px; margin: 12px 0; }
        .row { display: flex; justify-content: space-between; margin: 4px 0; }
        .label { color: #a0a0a0; }
        .value { font-weight: bold; }
        .ok { color: #2ecc71; }
        .warn { color: #e67e22; }
        .err { color: #e74c3c; }
        .muted { color: #666; }
        textarea, input[type=text] { width: 100%; padding: 10px; margin: 6px 0; box-sizing: border-box; background: #0f3460; border: 1px solid #1a1a5e; color: #e0e0e0; border-radius: 4px; font-family: monospace; }
        button { background: #d4a574; color: #1a1a2e; border: none; padding: 10px 24px; cursor: pointer; border-radius: 4px; font-weight: bold; margin-top: 8px; }
        button:hover { background: #c4955a; }
        .btn-secondary { background: #0f3460; color: #e0e0e0; }
        .success { color: #2ecc71; margin-top: 8px; }
        a { color: #d4a574; }
    </style>
</head>
<body>
    <h1>TRMNL Claude Usage</h1>

    <div class="card">
        <h2>Status</h2>
        <div class="row">
            <span class="label">Session Key</span>
            <span class="value {% if has_credentials %}ok{% else %}err{% endif %}">
                {{ "Configured" if has_credentials else "Not Set" }}
            </span>
        </div>
        <div class="row">
            <span class="label">Last Fetch</span>
            <span class="value">{{ last_fetch or "Never" }}</span>
        </div>
        <div class="row">
            <span class="label">Last Push to TRMNL</span>
            <span class="value">{{ last_push or "Never" }}</span>
        </div>
        {% if last_error %}
        <div class="row">
            <span class="label">Last Error</span>
            <span class="value err">{{ last_error }}</span>
        </div>
        {% endif %}
    </div>

    {% if last_usage %}
    <div class="card">
        <h2>Current Usage</h2>
        <div class="row">
            <span class="label">Session</span>
            <span class="value">{{ last_usage.session_pct }}%</span>
        </div>
        <div class="row">
            <span class="label">Opus Weekly</span>
            <span class="value">{{ last_usage.opus_weekly_pct }}%</span>
        </div>
        <div class="row">
            <span class="label">Sonnet Weekly</span>
            <span class="value">{{ last_usage.sonnet_weekly_pct }}%</span>
        </div>
        {% if last_usage.projected_at_reset is defined %}
        <div class="row">
            <span class="label">Projected at Reset</span>
            <span class="value">~{{ last_usage.projected_at_reset }}%</span>
        </div>
        <div class="row">
            <span class="label">Today</span>
            <span class="value">{{ last_usage.today_usage }}%</span>
        </div>
        <div class="row">
            <span class="label">Avg Daily Pace</span>
            <span class="value">{{ last_usage.avg_daily_pace }}%/day</span>
        </div>
        <div class="row">
            <span class="label">Budget/Day</span>
            <span class="value">{{ last_usage.budget_per_day }}%/day</span>
        </div>
        {% endif %}
    </div>
    {% endif %}

    <div class="card">
        <h2>Configuration</h2>
        <form method="post" action="/config">
            <label class="label">Session Key</label>
            <textarea name="session_key" rows="3" placeholder="Paste your Claude session key here">{{ session_key or "" }}</textarea>
            <label class="label">Organization ID</label>
            <input type="text" name="org_id" value="{{ org_id or "" }}" placeholder="e.g. abc123-def456-...">
            <button type="submit">Save & Fetch Now</button>
        </form>
        {% if saved %}
        <p class="success">Credentials saved. Fetching usage...</p>
        {% endif %}
    </div>

    <div class="card">
        <h2>Actions</h2>
        <form method="post" action="/fetch" style="display:inline;">
            <button type="submit" class="btn-secondary">Fetch Now</button>
        </form>
        <form method="post" action="/logout" style="display:inline; margin-left: 8px;">
            <button type="submit" class="btn-secondary">Logout</button>
        </form>
    </div>
</body>
</html>
```

**Step 3: Create the FastAPI app**

Create `src/app/main.py`:

```python
import logging
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeSerializer

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
        next_run_time=None,  # Don't run immediately on startup
    )
    scheduler.start()
    logger.info(f"Scheduler started: fetching every {FETCH_INTERVAL_MINUTES} min")
    # Run initial fetch after brief startup delay
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


@app.post("/config")
async def save_config(request: Request, session_key: str = Form(...), org_id: str = Form(...)):
    if not _is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)

    config.save_credentials(session_key.strip(), org_id.strip())
    # Trigger immediate fetch
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
        "saved": True,
    })


@app.post("/fetch")
async def manual_fetch(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)
    await usage_scheduler.fetch_and_push()
    return RedirectResponse(url="/", status_code=303)
```

**Step 4: Verify the app starts locally**

Run: `cd src && DATA_DIR=/tmp/trmnl-test TRMNL_WEBHOOK_UUID=test WEB_PASSWORD=test python -m uvicorn app.main:app --port 8085`
Expected: Server starts, accessible at http://localhost:8085, shows login page.

**Step 5: Commit**

```bash
git add src/app/main.py src/app/templates/
git commit -m "feat: web UI with login, status dashboard, and config form"
```

---

### Task 8: TRMNL Liquid Template

**Files:**
- Create: `trmnl-template.html` (reference file, pasted into TRMNL plugin editor)

This file is NOT deployed in the container — it's pasted into the TRMNL web UI Private Plugin editor.

**Step 1: Create the Liquid template**

Create `trmnl-template.html`:

```html
<div class="screen">
  <div class="view view--full">
    {% if status == "healthy" %}
    <div class="layout layout--col gap--space-between" style="height: 100%;">
      <div class="columns">
        <!-- Session Usage -->
        <div class="column">
          <span class="label label--underline">Session Usage</span>
          <div class="content content--center" style="margin: 12px 0;">
            <span class="value value--tnums" style="font-size: 48px;">{{ session_pct }}%</span>
          </div>
          <!-- Progress bar -->
          <div style="background: #ddd; height: 12px; border-radius: 6px; overflow: hidden; margin: 8px 0;">
            <div style="background: #000; height: 100%; width: {{ session_pct }}%; border-radius: 6px;"></div>
          </div>
          <span class="description">Resets at {{ session_reset }}</span>
        </div>
      </div>

      <!-- Weekly Breakdown -->
      <div class="columns" style="margin-top: 16px;">
        <div class="column">
          <span class="label label--underline">Opus Weekly</span>
          <span class="value value--tnums" style="font-size: 32px;">{{ opus_weekly_pct }}%</span>
          <div style="background: #ddd; height: 8px; border-radius: 4px; overflow: hidden; margin-top: 4px;">
            <div style="background: #000; height: 100%; width: {{ opus_weekly_pct }}%; border-radius: 4px;"></div>
          </div>
        </div>
        <div class="column">
          <span class="label label--underline">Sonnet Weekly</span>
          <span class="value value--tnums" style="font-size: 32px;">{{ sonnet_weekly_pct }}%</span>
          <div style="background: #ddd; height: 8px; border-radius: 4px; overflow: hidden; margin-top: 4px;">
            <div style="background: #000; height: 100%; width: {{ sonnet_weekly_pct }}%; border-radius: 4px;"></div>
          </div>
        </div>
      </div>

      <!-- Projections -->
      <div class="columns" style="margin-top: 16px;">
        <div class="column">
          <span class="label label--underline">Weekly Projected</span>
          <div class="content" style="margin-top: 4px;">
            <span class="description">At reset: <strong>~{{ projected_at_reset }}%</strong></span>
          </div>
          <div class="content" style="margin-top: 4px;">
            <span class="description">Today: {{ today_usage }}% &middot; Avg: {{ avg_daily_pace }}%/day</span>
          </div>
          <div class="content" style="margin-top: 4px;">
            <span class="description">Budget: {{ budget_per_day }}%/day remaining</span>
          </div>
        </div>
      </div>

      <!-- Updated timestamp -->
      <div style="margin-top: auto; padding-top: 8px;">
        <span class="description">Updated: {{ updated_at }}</span>
      </div>
    </div>

    {% elsif status == "expired" %}
    <div class="layout layout--col" style="height: 100%; justify-content: center; align-items: center; text-align: center;">
      <span class="value" style="font-size: 28px;">Session Key Expired</span>
      <div style="margin-top: 16px;">
        <span class="description">Update at:</span>
        <br>
        <span class="label" style="font-size: 18px;">{{ config_url }}</span>
      </div>
      {% if last_valid %}
      <div style="margin-top: 24px;">
        <span class="description">Last valid data: {{ last_valid }}</span>
      </div>
      {% endif %}
    </div>

    {% else %}
    <div class="layout layout--col" style="height: 100%; justify-content: center; align-items: center; text-align: center;">
      <span class="value" style="font-size: 28px;">Setup Required</span>
      <div style="margin-top: 16px;">
        <span class="description">Configure at:</span>
        <br>
        <span class="label" style="font-size: 18px;">{{ config_url }}</span>
      </div>
    </div>
    {% endif %}

    <div class="title_bar">
      <span class="title">Claude Usage</span>
      <span class="instance">esaipetch</span>
    </div>
  </div>
</div>
```

**Step 2: Commit**

```bash
git add trmnl-template.html
git commit -m "feat: TRMNL Liquid template for e-ink dashboard"
```

---

### Task 9: Deployment

**Step 1: Create directories on server**

```bash
ssh 192.168.200.7 "mkdir -p ~/dockerfiles-mserver/trmnl-claude && mkdir -p /var/docker/trmnl-claude/{src,data}"
```

**Step 2: Copy files to server**

```bash
# Copy docker-compose and Dockerfile
scp docker-compose.yml 192.168.200.7:~/dockerfiles-mserver/trmnl-claude/
scp Dockerfile 192.168.200.7:~/dockerfiles-mserver/trmnl-claude/

# Copy source code
scp -r src/app src/requirements.txt 192.168.200.7:/var/docker/trmnl-claude/src/

# Create .env file
scp .env.example 192.168.200.7:/var/docker/trmnl-claude/.env
```

Then SSH in and edit `/var/docker/trmnl-claude/.env` with actual values.

**Step 3: Build and start**

```bash
ssh 192.168.200.7 "cd ~/dockerfiles-mserver/trmnl-claude && docker compose up -d --build"
```

**Step 4: Verify**

- Open http://192.168.200.7:8085 — should see login page
- Log in with password from .env
- Paste session key and org ID, click "Save & Fetch Now"
- Verify usage data appears on status page
- Check TRMNL device updates on next refresh cycle

**Step 5: Set up TRMNL private plugin**

1. Go to trmnl.com → Plugins → Private Plugin → Create
2. Choose "Webhook" strategy
3. Copy the Webhook UUID into your `.env` file on the server
4. Paste the contents of `trmnl-template.html` into the Markup editor
5. Save the plugin
6. Restart the container: `ssh 192.168.200.7 "cd ~/dockerfiles-mserver/trmnl-claude && docker compose up -d --build"`

**Step 6: Commit final state**

```bash
git add -A
git commit -m "feat: deployment config and documentation complete"
```

---

### Task 10: End-to-End Verification

**Step 1: Run all tests locally**

```bash
cd src && pip install -r requirements.txt -r requirements-dev.txt && python -m pytest tests/ -v
```
Expected: All tests pass.

**Step 2: Verify container logs**

```bash
ssh 192.168.200.7 "docker logs trmnl-claude --tail 20"
```
Expected: See "Scheduler started" and successful fetch/push logs.

**Step 3: Verify TRMNL webhook received data**

Check the TRMNL plugin page — it should show the merge_variables JSON and a preview of the rendered screen.

**Step 4: Wait for device refresh**

TRMNL device should show the dashboard on its next playlist wake cycle.
