import logging
from datetime import datetime, timezone
from typing import Any

from app.claude_client import ClaudeClient, AuthError, UsageData
from app.config import ConfigManager
from app.projection import ProjectionEngine
from app.trmnl_client import TRMNLClient

logger = logging.getLogger(__name__)


class UsageScheduler:
    def __init__(self, data_dir: str = "/app/data"):
        self.config = ConfigManager(data_dir=data_dir)
        self.projection = ProjectionEngine(data_dir=data_dir)

    def _get_trmnl(self, cfg: dict) -> TRMNLClient | None:
        webhook_url = cfg.get("webhook_url") or ""
        if not webhook_url:
            return None
        return TRMNLClient(webhook_url=webhook_url)

    async def fetch_and_push(self) -> None:
        cfg = self.config.load()
        trmnl = self._get_trmnl(cfg)

        if not self.config.has_credentials():
            logger.info("No credentials configured, pushing setup_required")
            if trmnl:
                try:
                    await trmnl.push(trmnl.build_payload("setup_required", {}, {}))
                except Exception as e:
                    logger.error(f"Failed to push setup_required: {e}")
            return

        session_key = cfg["session_key"]
        org_id = cfg["org_id"]

        try:
            client = ClaudeClient(session_key, org_id)
            usage = await client.fetch_usage()
            self.config.update_fetch_time()
            self.config.save_last_error(None)

            # Record snapshot for projections
            self.projection.record_if_needed(usage.weekly_pct)

            # Format reset time for display
            session_reset_str = _format_time(usage.session_reset)

            # Compute projections
            projections = self.projection.compute_projections(
                current_pct=usage.weekly_pct,
                reset_time=usage.weekly_reset,
            )

            usage_dict = {
                "session_pct": round(usage.session_pct),
                "session_reset": session_reset_str,
                "opus_weekly_pct": round(usage.opus_weekly_pct),
                "sonnet_weekly_pct": round(usage.sonnet_weekly_pct),
            }

            self.config.save_last_usage(usage_dict | projections)

            if trmnl:
                payload = trmnl.build_payload("healthy", usage_dict, projections)
                pushed = await trmnl.push(payload)
                if pushed:
                    self.config.update_push_time()
                    logger.info(f"Pushed usage: session={usage.session_pct}%, weekly={usage.weekly_pct}%")
                else:
                    logger.warning("TRMNL push returned non-200")

        except AuthError as e:
            logger.warning(f"Auth error: {e}")
            self.config.save_last_error(str(e))
            if trmnl:
                last_fetch = cfg.get("last_fetch")
                last_valid = _format_datetime(last_fetch) if last_fetch else None
                try:
                    await trmnl.push(trmnl.build_payload(
                        "expired", {}, {},
                        error_message="Session Key Expired",
                        last_valid=last_valid,
                    ))
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Fetch error: {e}")
            self.config.save_last_error(str(e))


def _format_time(dt: datetime | None) -> str:
    if dt is None:
        return ""
    local = dt.astimezone()
    return local.strftime("%-I:%M %p")


def _format_datetime(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        local = dt.astimezone()
        return local.strftime("%b %-d, %-I:%M %p")
    except (ValueError, AttributeError):
        return iso_str
