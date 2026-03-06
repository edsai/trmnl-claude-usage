import pytest
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
