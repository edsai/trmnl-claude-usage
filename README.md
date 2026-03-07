# trmnl-claude-usage

Display your Claude Pro/Team usage stats on a [TRMNL](https://usetrmnl.com/) e-ink dashboard.

![TRMNL Claude Usage Dashboard](screenshot.jpg)

## Features

- Session and weekly usage percentages (Opus & Sonnet)
- Usage projections: projected % at reset, daily pace, remaining budget per day
- "Hits limit" warning when you're on track to exhaust your quota before reset
- Web UI for configuration (session key, org selection, webhook URL)
- Auto-refreshes on a configurable interval (default: 15 minutes)
- Expired session key detection with on-screen alert

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- A [TRMNL](https://usetrmnl.com/) account with a Private Plugin webhook
- A Claude Pro or Team subscription on [claude.ai](https://claude.ai)

## Setup

> This plugin has been submitted to the TRMNL marketplace. If it's available there, install it and skip to step 4.

### 1. Create a TRMNL Private Plugin

- Go to [trmnl.com/plugins](https://trmnl.com/plugins) and click **Private Plugin**
- Give it a name (e.g. "Claude Usage")
- Set **Strategy** to **Webhook**
- A **Webhook URL** will appear at the bottom of the page (starts with `https://trmnl.com/api/custom_plugins/...`) — copy this, you'll need it in step 5

### 2. Paste the markup

- Click **Edit Markup**
- You'll see tabs for **Full**, **Half horizontal**, **Half vertical**, and **Quadrant**
- Open [`src/app/trmnl-template.html`](src/app/trmnl-template.html) from this repo
- The file contains 4 `<div class="screen">` blocks, one for each layout size
- Copy the **contents inside** each `<div class="view">` (not the `<div class="screen">` or `<div class="view">` wrappers themselves) into the matching tab:
  - 1st block -> **Full**
  - 2nd block -> **Half horizontal**
  - 3rd block -> **Half vertical**
  - 4th block -> **Quadrant**
- Save each tab

### 3. Save the plugin

- Set **Refresh rate** to **Hourly** (the app pushes data on its own schedule, TRMNL just re-renders periodically)
- Click **Save**

### 4. Start the container

```bash
git clone https://github.com/edsai/trmnl-claude-usage.git
cd trmnl-claude-usage
cp .env.example .env
# Edit .env — set WEB_PASSWORD to something secure
docker compose up -d
```

### 5. Configure the app

Open `http://your-server:8085` in your browser and log in with your `WEB_PASSWORD`.

- **Webhook URL** — paste the URL from step 1 into the TRMNL Plugin Setup section and click Save
- **Session Key** — paste your Claude `sessionKey` cookie (the web UI has a "How to get your Session Key" guide with step-by-step instructions)
- **Organization** — select your org and click Save & Fetch Now

The app will immediately fetch your usage and push it to TRMNL. It continues fetching automatically every 15 minutes.

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `WEB_PASSWORD` | Yes | `changeme` | Password for the web config UI |
| `FETCH_INTERVAL_MINUTES` | No | `15` | How often to fetch usage data (minutes) |

## How Projections Work

The app takes a daily snapshot of your weekly usage percentage. Using the rate of change across snapshots, it calculates:

- **Projected at reset**: Where your usage will be when the weekly quota resets
- **Avg daily pace**: Your average daily consumption rate
- **Budget per day**: How much you can use per day to stay within limits
- **Hits limit**: If you're on pace to hit 100% before reset, shows when

Snapshots reset automatically when a weekly quota reset is detected.

## License

[MIT](LICENSE)
