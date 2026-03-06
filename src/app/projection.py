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
