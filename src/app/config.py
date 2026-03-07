from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ConfigManager:
    def __init__(self, data_dir: str = "/app/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.data_dir / "config.json"

    def load(self) -> dict[str, Any]:
        if self.config_path.exists():
            with open(self.config_path) as f:
                return json.load(f)
        return self._defaults()

    def _defaults(self) -> dict[str, Any]:
        return {
            "session_key": None,
            "org_id": None,
            "webhook_url": None,
            "last_fetch": None,
            "last_push": None,
            "last_usage": None,
            "last_error": None,
        }

    def _save(self, cfg: dict[str, Any]) -> None:
        with open(self.config_path, "w") as f:
            json.dump(cfg, f, indent=2)

    def save_credentials(self, session_key: str, org_id: str) -> None:
        cfg = self.load()
        cfg["session_key"] = session_key
        cfg["org_id"] = org_id
        self._save(cfg)

    def save_webhook_url(self, webhook_url: str) -> None:
        cfg = self.load()
        cfg["webhook_url"] = webhook_url
        self._save(cfg)

    def has_credentials(self) -> bool:
        cfg = self.load()
        return bool(cfg.get("session_key")) and bool(cfg.get("org_id"))

    def update_fetch_time(self) -> None:
        cfg = self.load()
        cfg["last_fetch"] = datetime.now(timezone.utc).isoformat()
        self._save(cfg)

    def update_push_time(self) -> None:
        cfg = self.load()
        cfg["last_push"] = datetime.now(timezone.utc).isoformat()
        self._save(cfg)

    def save_last_usage(self, usage: dict[str, Any]) -> None:
        cfg = self.load()
        cfg["last_usage"] = usage
        self._save(cfg)

    def save_last_error(self, error: str | None) -> None:
        cfg = self.load()
        cfg["last_error"] = error
        self._save(cfg)
