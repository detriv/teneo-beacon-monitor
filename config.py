"""Settings management for Teneo Beacon Monitor."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path.home() / ".config" / "teneo-beacon" / "bot.env"),
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

    # State
    state_file: str = str(Path.home() / ".config" / "teneo-beacon" / "boost_state.json")
    notify_file: str = str(Path.home() / ".config" / "teneo-beacon" / "boost_ready.txt")

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_enabled: bool = False

    # Webhook (optional) — set to enable external notifications
    webhook_url: str = ""
    webhook_enabled: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8765
