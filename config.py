"""Settings management for Teneo Beacon Monitor."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = directory where this config.py lives
BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # Read from FastAPI Cloud env vars or local .env file
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Auth
    teneo_auth_token: str = ""

    # API
    teneo_api_url: str = "https://gateway.teneo.pro/api/user/beacon"
    teneo_origin: str = "https://hub.teneo.pro"
    teneo_referer: str = "https://hub.teneo.pro/"

    # Monitor
    check_interval_seconds: int = 3600  # 1 hour

    # State — stored in project's data/ directory (standalone, portable)
    data_dir: str = str(BASE_DIR / "data")
    state_file: str = ""  # computed in model_post_init
    notify_file: str = ""  # computed in model_post_init

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_enabled: bool = False

    # Webhook (optional) — set to enable external notifications
    webhook_url: str = ""
    webhook_enabled: bool = False

    # Server (FastAPI Cloud sets PORT automatically)
    host: str = "0.0.0.0"
    port: int = int(os.getenv("PORT", "8765"))

    def model_post_init(self, __context):
        # Resolve state/notify files relative to data_dir
        data_dir = Path(self.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        if not self.state_file:
            self.state_file = str(data_dir / "boost_state.json")
        if not self.notify_file:
            self.notify_file = str(data_dir / "boost_ready.txt")
