import json
import os
import tempfile
import pytest
from pathlib import Path


def test_config_loads_defaults_when_no_file():
    from app.config import ConfigManager
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ConfigManager(data_dir=tmpdir)
        cfg = mgr.load()
        assert cfg["session_key"] is None
        assert cfg["org_id"] is None
        assert cfg["last_fetch"] is None
        assert cfg["last_push"] is None


def test_config_saves_and_loads_session_key():
    from app.config import ConfigManager
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ConfigManager(data_dir=tmpdir)
        mgr.save_credentials("sk-test-123", "org-abc")
        cfg = mgr.load()
        assert cfg["session_key"] == "sk-test-123"
        assert cfg["org_id"] == "org-abc"


def test_config_updates_timestamps():
    from app.config import ConfigManager
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ConfigManager(data_dir=tmpdir)
        mgr.update_fetch_time()
        cfg = mgr.load()
        assert cfg["last_fetch"] is not None


def test_config_updates_push_time():
    from app.config import ConfigManager
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ConfigManager(data_dir=tmpdir)
        mgr.update_push_time()
        cfg = mgr.load()
        assert cfg["last_push"] is not None


def test_config_stores_last_usage():
    from app.config import ConfigManager
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ConfigManager(data_dir=tmpdir)
        usage = {"session_pct": 42, "opus_weekly_pct": 10}
        mgr.save_last_usage(usage)
        cfg = mgr.load()
        assert cfg["last_usage"]["session_pct"] == 42


def test_config_has_credentials():
    from app.config import ConfigManager
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = ConfigManager(data_dir=tmpdir)
        assert mgr.has_credentials() is False
        mgr.save_credentials("key", "org")
        assert mgr.has_credentials() is True
