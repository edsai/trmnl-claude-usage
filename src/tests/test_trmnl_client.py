import pytest
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
    assert mv["config_url"]


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
