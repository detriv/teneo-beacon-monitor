"""Teneo Beacon Monitor — FastAPI Application."""
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from beacon_service import BeaconService
from config import Settings

settings = Settings()
service = BeaconService(settings)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("teneo-beacon")

scheduler = BackgroundScheduler()


def run_monitor_check():
    """Scheduled job: check cooldown, send notification when ready."""
    try:
        result = service.check_and_notify()
        status = result["status"]
        cooldown = result["cooldown_remaining"]

        log.info(
            "Power: %.2fx | Unclaimed: %s | Boosts: %s | Cooldown: %ds (%.1fh)",
            status.get("beaconPower", 100) / 100,
            status.get("unclaimedFragments", 0),
            status.get("totalBoosts", 0),
            cooldown,
            cooldown / 3600,
        )

        if result["notification"]:
            log.info("🚀 BOOST READY — sending notification")
            service.write_notify_file(result["notification"])
            # Send Telegram notification
            service.send_telegram(result["notification"])
            # Send webhook if configured
            if settings.webhook_enabled:
                service.send_webhook(result["notification"])

    except Exception as e:
        log.error("Monitor check failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log.info("Teneo Beacon Monitor starting — interval: %ds", settings.check_interval_seconds)
    # Run once immediately on startup
    run_monitor_check()
    # Schedule recurring checks
    scheduler.add_job(
        run_monitor_check,
        "interval",
        seconds=settings.check_interval_seconds,
        id="teneo_boost_check",
        replace_existing=True,
    )
    scheduler.start()
    yield
    # Shutdown
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Teneo Beacon Monitor",
    description="Monitor Teneo Protocol Beacon boost cooldown and get notified when claim is ready.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    return {
        "service": "Teneo Beacon Monitor",
        "version": "1.0.0",
        "endpoints": ["/status", "/check", "/health"],
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/status")
async def get_status():
    """Get current beacon status from Teneo API."""
    try:
        status = service.fetch_status()
        return {
            "beaconPower": status.get("beaconPower", 100) / 100,
            "unclaimedFragments": status.get("unclaimedFragments", 0),
            "totalFragments": status.get("fragments", 0),
            "totalBoosts": status.get("totalBoosts", 0),
            "consecutiveBoosts": status.get("consecutiveBoosts", 0),
            "cooldownRemaining": status.get("cooldownRemaining", 0),
            "cooldownHours": round(status.get("cooldownRemaining", 0) / 3600, 2),
            "connectedNodes": status.get("connectedNodes", 0),
            "fragmentsPerHour": status.get("fragmentsPerHour", 10),
            "lastBoostAt": status.get("lastBoostAt"),
            "earlyBoostFee": status.get("earlyBoostFee", 0),
            "boostReady": status.get("cooldownRemaining", 0) <= 0,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Teneo API error: {str(e)}")


@app.post("/check")
async def trigger_check():
    """Manually trigger a cooldown check. Returns notification if ready."""
    result = service.check_and_notify()
    return {
        "cooldownRemaining": result["cooldown_remaining"],
        "boostReady": result["cooldown_remaining"] <= 0,
        "notification": result["notification"],
    }


@app.get("/notify", response_class=PlainTextResponse)
async def get_last_notification():
    """Return the last ready notification (if any)."""
    from pathlib import Path
    notify_path = Path(settings.notify_file)
    if notify_path.exists():
        return notify_path.read_text()
    return "No notification yet — boost not ready."


@app.post("/test-notify")
async def test_telegram_notification():
    """Send a test notification to Telegram (if configured)."""
    if not settings.telegram_enabled:
        return {"status": "error", "message": "Telegram not enabled. Set TELEGRAM_ENABLED=true."}
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return {"status": "error", "message": "Telegram bot token or chat ID not set."}

    test_message = (
        "🧪 Teneo Beacon Monitor — Test Notification\n"
        "✅ Telegram integration is working!\n"
        "📊 This is a test message from your FastAPI monitor."
    )

    success = service.send_telegram(test_message)
    if success:
        return {"status": "ok", "message": "Test notification sent to Telegram."}
    else:
        return {"status": "error", "message": "Failed to send Telegram notification. Check logs."}
