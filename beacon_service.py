"""Core beacon service — API calls, state management, notification formatting."""
import json
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests
from telegram import Bot

from config import Settings

log = logging.getLogger(__name__)


class BeaconService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._ensure_state_file()

    def _ensure_state_file(self):
        state_path = Path(self.settings.state_file)
        if not state_path.exists():
            state_path.write_text(json.dumps({
                "last_notified_cooldown": None,
                "last_ready_at": None,
                "last_cooldown_remaining": None,
            }, indent=2))

    def fetch_status(self) -> dict:
        """Call Teneo Hub API and return beacon status."""
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.settings.teneo_auth_token}",
            "Origin": self.settings.teneo_origin,
            "Referer": self.settings.teneo_referer,
        }
        resp = requests.get(
            self.settings.teneo_api_url,
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def load_state(self) -> dict:
        state_path = Path(self.settings.state_file)
        if state_path.exists():
            return json.loads(state_path.read_text())
        return {"last_notified_cooldown": None}

    def save_state(self, state: dict):
        state_path = Path(self.settings.state_file)
        state_path.write_text(json.dumps(state, indent=2))

    def format_notification(self, status: dict) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        cooldown = status.get("cooldownRemaining", 0)
        beacon_power = status.get("beaconPower", 100)
        unclaimed = status.get("unclaimedFragments", 0)
        total_boosts = status.get("totalBoosts", 0)
        fragments = status.get("fragments", 0)
        last_boost = status.get("lastBoostAt", "N/A")
        power_multiplier = beacon_power / 100

        lines = [
            "🔔 Teneo Boost — Claim Ready!",
            "",
            f"⏰ Waktu: {now}",
            f"📊 Beacon Power: {power_multiplier:.2f}x",
            f"📦 Unclaimed Fragments: {unclaimed}",
            f"💰 Total Fragments: {fragments}",
            f"🔄 Total Boosts: {total_boosts}",
            f"🕐 Last Boost: {last_boost}",
            "",
            "👉 Buka app / hub.teneo.pro untuk claim boost!",
        ]

        if cooldown <= 0:
            lines.insert(1, "✅ Cooldown habis — SIAP CLAIM!")
        else:
            hours_left = cooldown / 3600
            lines.insert(1, f"⏳ Cooldown: {hours_left:.1f} jam lagi")

        return "\n".join(lines)

    def check_and_notify(self) -> dict:
        """
        Fetch status, check cooldown, save state.
        Returns dict with status, notification (or None), cooldown_remaining.
        """
        status = self.fetch_status()
        cooldown = status.get("cooldownRemaining", 0)
        state = self.load_state()
        now_ts = int(time.time())
        notification = None

        if cooldown <= 0:
            if state.get("last_notified_cooldown") != "ready":
                notification = self.format_notification(status)
                state["last_notified_cooldown"] = "ready"
                state["last_ready_at"] = now_ts
        else:
            state["last_notified_cooldown"] = "cooling"
            state["last_cooldown_remaining"] = cooldown

        self.save_state(state)

        return {
            "status": status,
            "notification": notification,
            "cooldown_remaining": cooldown,
        }

    def send_webhook(self, message: str) -> bool:
        """Send notification to webhook if configured."""
        if not self.settings.webhook_enabled or not self.settings.webhook_url:
            return False
        try:
            resp = requests.post(
                self.settings.webhook_url,
                json={"text": message},
                timeout=10,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            log.error("Webhook failed: %s", e)
            return False

    async def send_telegram(self, message: str) -> bool:
        """Send notification to Telegram if configured (async)."""
        if not self.settings.telegram_enabled or not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            return False
        try:
            bot = Bot(token=self.settings.telegram_bot_token)
            response = await bot.send_message(
                chat_id=self.settings.telegram_chat_id,
                text=message,
                disable_web_page_preview=True,
            )
            log.info("Telegram sent: message_id=%s chat=%s", response.message_id, self.settings.telegram_chat_id)
            return True
        except Exception as e:
            log.error("Telegram send failed: %s", e)
            return False

    def write_notify_file(self, message: str):
        """Write notification to file for external pickup."""
        Path(self.settings.notify_file).write_text(message)
