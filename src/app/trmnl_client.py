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
