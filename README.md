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

## TRMNL Template

Create a **Private Plugin** in your TRMNL dashboard, then paste the following Liquid/HTML template into the **Markup** editor:

<details>
<summary>Click to expand template</summary>

```html
<div class="screen">
  <div class="view view--full">
    {% if status == "healthy" %}
    <div class="layout layout--col gap--space-between">

      <!-- Row 1: Session hero + weekly stats -->
      <div class="grid stretch-y">
        <div class="col col--span-3">
          <div class="item grow">
            <div class="meta"></div>
            <div class="content flex flex--col flex--center-x flex--center-y" style="width: 100%; align-items: center; justify-content: center;">
              <span class="value value--xxlarge" data-fit-value="true">{{ session_pct }}%</span>
              <span class="label label--underline">Session</span>
            </div>
          </div>
        </div>
        <div class="col col--span-3 gap--medium">
          <div class="item">
            <div class="meta"></div>
            <div class="content">
              <span class="label">Resets at {{ session_reset }}</span>
            </div>
          </div>
          <div style="background: #ddd; height: 8px; border-radius: 4px; overflow: hidden;">
            <div style="background: #000; height: 100%; width: {{ session_pct }}%; border-radius: 4px;"></div>
          </div>
          <div class="item">
            <div class="meta"></div>
            <div class="content">
              <span class="value value--large" data-fit-value="true">{{ opus_weekly_pct }}%</span>
              <span class="label">Opus Weekly</span>
            </div>
          </div>
          <div class="item">
            <div class="meta"></div>
            <div class="content">
              <span class="value value--large" data-fit-value="true">{{ sonnet_weekly_pct }}%</span>
              <span class="label">Sonnet Weekly</span>
            </div>
          </div>
        </div>
      </div>

      <div class="divider"></div>

      <!-- Row 2: Projections -->
      <div class="columns">
        {% if hits_limit_date != "" %}
        <div class="column">
          <span class="label label--underline">Hits Limit</span>
          <span class="value value--large" data-fit-value="true">{{ hits_limit_date }}</span>
          <span class="description">in {{ hits_limit_days }}</span>
        </div>
        {% else %}
        <div class="column">
          <span class="label label--underline">At Reset</span>
          <span class="value value--large" data-fit-value="true">~{{ projected_at_reset }}%</span>
        </div>
        {% endif %}
        <div class="column">
          <span class="label label--underline">Today</span>
          <span class="value value--large" data-fit-value="true">{{ today_usage }}%</span>
        </div>
        <div class="column">
          <span class="label label--underline">Avg Pace</span>
          <span class="value value--large" data-fit-value="true">{{ avg_daily_pace }}%</span>
          <span class="label">/day</span>
        </div>
        <div class="column">
          <span class="label label--underline">Budget</span>
          <span class="value value--large" data-fit-value="true">{{ budget_per_day }}%</span>
          <span class="label">/day</span>
        </div>
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
      <span class="instance">{{ updated_at }}</span>
    </div>
  </div>
</div>
```

</details>

## How Projections Work

The app takes a daily snapshot of your weekly usage percentage. Using the rate of change across snapshots, it calculates:

- **Projected at reset**: Where your usage will be when the weekly quota resets
- **Avg daily pace**: Your average daily consumption rate
- **Budget per day**: How much you can use per day to stay within limits
- **Hits limit**: If you're on pace to hit 100% before reset, shows when

Snapshots reset automatically when a weekly quota reset is detected.

## License

[MIT](LICENSE)
