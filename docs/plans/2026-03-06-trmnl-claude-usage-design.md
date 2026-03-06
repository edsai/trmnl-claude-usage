# TRMNL Claude Usage Dashboard - Design Doc

## Overview

A Docker container running on 192.168.200.7 that fetches Claude usage data every 30 minutes and pushes it to a TRMNL e-ink dashboard via webhook. Includes a password-protected web UI for session key management.

## Architecture

```
Claude API  -->  Container (30-min loop)  -->  TRMNL Webhook API  -->  TRMNL device
                      |
                 Web UI on :8085
                 (paste session key, view status)
```

## Data Displayed

- **Session usage**: 5-hour rolling window utilization % with progress bar, reset time
- **Weekly Opus/Sonnet breakdown**: separate % for each model
- **Projections**: projected % at weekly reset, today's consumption, avg daily pace, remaining budget/day

## Container Components

### Python App (FastAPI + APScheduler)

- `app.py` - FastAPI app: web UI routes + background scheduler
- `claude_client.py` - Fetches from Claude API using session key cookie, parses usage JSON
- `trmnl_client.py` - POSTs merge_variables to `https://trmnl.com/api/custom_plugins/{UUID}`
- `projection.py` - Daily snapshot tracker + projection calculations (port of Swift logic)
- `config.py` - Manages persistent config (session key, org ID) in JSON file on volume

### Credential & Config Storage

- `TRMNL_WEBHOOK_UUID` and `WEB_PASSWORD`: env vars in `/var/docker/trmnl-claude/.env`
- Claude session key + org ID: JSON file at `/var/docker/trmnl-claude/data/config.json` (updated via web UI)
- Daily snapshots: JSON file at `/var/docker/trmnl-claude/data/snapshots.json`

### Web UI (port 8085, password-protected)

Single HTML page showing:
- Session key status (set/not set, last validated)
- Last successful fetch timestamp
- Current usage data (session %, weekly stats, projections)
- Last push to TRMNL timestamp
- Form to paste new session key and org ID

Authentication: single password via `WEB_PASSWORD` env var, cookie-based session.

## Server Integration

Follows existing patterns on 192.168.200.7:

- Project dir: `~/dockerfiles-mserver/trmnl-claude/`
- Data/config: `/var/docker/trmnl-claude/`
- Source code: `/var/docker/trmnl-claude/src/`
- Network: `npm-network` (external)
- Port: 8085

### docker-compose.yml

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

### .env file

```
TRMNL_WEBHOOK_UUID=<your-uuid-from-trmnl>
WEB_PASSWORD=<your-password>
```

## TRMNL Private Plugin Setup

Create a Private Plugin in TRMNL's web UI with webhook strategy. The Liquid template handles three states.

### merge_variables JSON

```json
{
  "merge_variables": {
    "status": "healthy|expired|setup_required",
    "session_pct": 67,
    "session_reset": "2:45 PM",
    "opus_weekly_pct": 42,
    "sonnet_weekly_pct": 28,
    "projected_at_reset": 71,
    "today_usage": 8.0,
    "avg_daily_pace": 12.0,
    "budget_per_day": 9.6,
    "updated_at": "10:30 AM",
    "error_message": "Session Key Expired",
    "config_url": "http://192.168.200.7:8085",
    "last_valid": "Mar 5, 2:30 PM"
  }
}
```

### Liquid Template (entered in TRMNL plugin editor)

Uses TRMNL Framework CSS classes. Three states:

1. **healthy** - Full dashboard with session %, weekly Opus/Sonnet, projections
2. **expired** - Warning message with config URL and last valid data timestamp
3. **setup_required** - Setup instructions with config URL

### Screen Layout (800x480 e-ink, healthy state)

```
+--------------------------------------+
|                                      |
|   Session Usage          67%         |
|   [progress bar]                     |
|   Resets at 2:45 PM                  |
|                                      |
|   +-------------+-------------+      |
|   | Opus Weekly  | Sonnet Wkly |      |
|   |    42%       |    28%      |      |
|   | [progress]   | [progress]  |      |
|   +-------------+-------------+      |
|                                      |
|   Weekly Projected: ~71% at reset    |
|   Today: 8%  |  Avg: 12%/day        |
|   Budget: 9.6%/day remaining         |
|                                      |
|   Updated: 10:30 AM                  |
| -------------------------------------|
| Claude Usage                esaipetch|
+--------------------------------------+
```

## Projection Logic (Python port)

Ported from Claude Usage Tracker's Swift implementation (`DailyConsumptionTracker.swift`).

### Daily Snapshots

- Record weekly % at midnight each day
- Detect weekly resets (% drops > 5 points) and clear history
- Keep up to 8 days of snapshots

### Calculations

- **averageDailyPace**: `(current% - first_snapshot%) / elapsed_days`
- **projectedAtReset**: `current% + remaining_days * avgPace` (capped at 100)
- **todayConsumption**: `current% - today_midnight_snapshot%`
- **remainingBudgetPerDay**: `(100 - current%) / days_remaining`

Simplified vs Swift: no exponentially-weighted regression (unnecessary at 30-min sample intervals).

## Refresh Schedule

- Container fetches from Claude API: every 30 minutes
- TRMNL plugin refresh: 15 or 30 minutes (configured in TRMNL UI)
- TRMNL device wake: per playlist schedule

## Tech Stack

- Python 3.12-alpine
- FastAPI + Uvicorn
- APScheduler
- httpx (async HTTP client)
- Jinja2 (web UI templates)
