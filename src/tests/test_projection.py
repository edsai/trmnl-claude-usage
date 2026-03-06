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
        snap = DailySnapshot(
            date=(datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat(),
            weekly_pct=80.0,
            day_of_week=3,
        )
        eng.save_snapshots([snap.to_dict()])
        eng.record_if_needed(weekly_pct=5.0)
        snaps = eng.load_snapshots()
        assert len(snaps) == 1
        assert snaps[0]["weekly_pct"] == 5.0


def test_average_daily_pace():
    with tempfile.TemporaryDirectory() as tmpdir:
        eng = _engine(tmpdir)
        two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
        eng.save_snapshots([{
            "date": two_days_ago,
            "weekly_pct": 10.0,
            "day_of_week": 1,
        }])
        pace = eng.average_daily_pace(current_pct=30.0)
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
