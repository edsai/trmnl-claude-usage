import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from app.scheduler import UsageScheduler


@pytest.fixture
def scheduler():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = UsageScheduler(
            webhook_uuid="test-uuid",
            data_dir=tmpdir,
        )
        yield s


@pytest.mark.asyncio
async def test_fetch_and_push_healthy(scheduler):
    mock_usage_data = MagicMock()
    mock_usage_data.session_pct = 67.0
    mock_usage_data.weekly_pct = 35.0
    mock_usage_data.opus_weekly_pct = 42.0
    mock_usage_data.sonnet_weekly_pct = 28.0
    mock_usage_data.session_reset = datetime.now(timezone.utc) + timedelta(hours=3)
    mock_usage_data.weekly_reset = datetime.now(timezone.utc) + timedelta(days=5)
    mock_usage_data.to_dict.return_value = {
        "session_pct": 67.0,
        "opus_weekly_pct": 42.0,
        "sonnet_weekly_pct": 28.0,
    }

    scheduler.config.save_credentials("sk-test", "org-test")

    with patch("app.scheduler.ClaudeClient") as MockClient:
        instance = MockClient.return_value
        instance.fetch_usage = AsyncMock(return_value=mock_usage_data)

        with patch.object(scheduler.trmnl, "push", new_callable=AsyncMock, return_value=True):
            await scheduler.fetch_and_push()

    cfg = scheduler.config.load()
    assert cfg["last_fetch"] is not None
    assert cfg["last_push"] is not None
    assert cfg["last_error"] is None


@pytest.mark.asyncio
async def test_fetch_and_push_no_credentials(scheduler):
    with patch.object(scheduler.trmnl, "push", new_callable=AsyncMock, return_value=True) as mock_push:
        await scheduler.fetch_and_push()
    # Should have pushed setup_required
    mock_push.assert_called_once()
    payload = mock_push.call_args[0][0]
    assert payload["merge_variables"]["status"] == "setup_required"


@pytest.mark.asyncio
async def test_fetch_and_push_auth_error(scheduler):
    from app.claude_client import AuthError
    scheduler.config.save_credentials("sk-expired", "org-test")

    with patch("app.scheduler.ClaudeClient") as MockClient:
        instance = MockClient.return_value
        instance.fetch_usage = AsyncMock(side_effect=AuthError("expired"))

        with patch.object(scheduler.trmnl, "push", new_callable=AsyncMock, return_value=True):
            await scheduler.fetch_and_push()

    cfg = scheduler.config.load()
    assert cfg["last_error"] is not None
