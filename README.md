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

## Quick Start

```bash
git clone https://github.com/edsai/trmnl-claude-usage.git
cd trmnl-claude-usage
cp .env.example .env
# Edit .env with your values
docker compose up -d
```

Then open `http://localhost:8085` in your browser to configure.

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `TRMNL_WEBHOOK_UUID` | Yes | — | Your TRMNL Private Plugin webhook UUID |
| `WEB_PASSWORD` | Yes | `changeme` | Password for the web config UI |
| `FETCH_INTERVAL_MINUTES` | No | `15` | How often to fetch usage data (minutes) |

### Web UI Setup

1. Open `http://localhost:8085` and log in with your `WEB_PASSWORD`
2. Paste your `sessionKey` cookie from claude.ai (DevTools > Application > Cookies)
3. Select your organization
4. Enter your TRMNL webhook URL (`https://usetrmnl.com/api/custom_plugins/YOUR_UUID`)

## TRMNL Plugin Setup

> This plugin has been submitted to the TRMNL marketplace. If it's available there, just install it directly and skip to step 6. Otherwise, follow these steps to create a Private Plugin.

### 1. Create the plugin

- Go to [trmnl.com/plugins](https://trmnl.com/plugins) and click **Private Plugin**
- Give it a name (e.g. "Claude Usage")

### 2. Set the strategy

- In the plugin settings, set **Strategy** to **Webhook**
- A **Webhook URL** will appear at the bottom of the page (starts with `https://trmnl.com/api/custom_plugins/...`)
- Copy this URL - you'll need it in step 6

### 3. Paste the markup

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

### 4. Set the refresh rate

- Back in plugin settings, set **Refresh rate** to **Hourly** (the app pushes data on its own schedule, TRMNL just needs to re-render periodically)

### 5. Save the plugin

- Click **Save**

### 6. Configure the app

- Open the web UI at `http://localhost:8085`
- Paste the **Webhook URL** from step 2 into the TRMNL Plugin Setup section
- Paste your Claude **sessionKey** cookie (see the "How to get your Session Key" guide in the web UI)
- Select your organization and save

## How Projections Work

The app takes a daily snapshot of your weekly usage percentage. Using the rate of change across snapshots, it calculates:

- **Projected at reset**: Where your usage will be when the weekly quota resets
- **Avg daily pace**: Your average daily consumption rate
- **Budget per day**: How much you can use per day to stay within limits
- **Hits limit**: If you're on pace to hit 100% before reset, shows when

Snapshots reset automatically when a weekly quota reset is detected.

## License

[MIT](LICENSE)
