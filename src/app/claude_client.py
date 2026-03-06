from dataclasses import dataclass
from datetime import datetime
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
