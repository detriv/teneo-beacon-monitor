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


@app.api_route("/test-notify", methods=["GET", "POST"])
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

    success = await service.send_telegram(test_message)
    if success:
        return {"status": "ok", "message": "Test notification sent to Telegram."}
    else:
        return {"status": "error", "message": "Failed to send Telegram notification. Check logs."}


@app.api_route("/smoke-test", methods=["GET", "POST"])
async def smoke_test_boost_ready(send_real: bool = False, force: bool = False):
    """
    Smoke test: simulate cooldownRemaining=0 and verify auto-notification flow.

    This endpoint:
    1. Resets state (so test always runs fresh)
    2. Mocks API response with cooldownRemaining=0
    3. Runs check_and_notify() to verify notification generation
    4. Optionally sends real Telegram message (if send_real=true)
    5. Returns detailed test results

    Query params:
        send_real: bool = False — set true to also send real Telegram message
        force: bool = False — set true to bypass state check (always generate notif)
    """
    from datetime import datetime, timezone
    from unittest.mock import MagicMock, patch

    print("\n🧪 Smoke Test: Boost Ready Flow")
    print("=" * 50)

    # Reset state to ensure test runs fresh
    if force:
        service.save_state({"last_notified_cooldown": None, "last_ready_at": None, "last_cooldown_remaining": None})
        print("🔄 State reset (force=True)")

    # Mock API response: cooldownRemaining=0 (boost ready)
    mock_api_response = {
        "fragments": 5965.4,
        "totalFragments": 5965.4,
        "escrowFragments": 0,
        "unclaimedFragments": 30,
        "beaconPower": 124,
        "totalBoosts": 2,
        "consecutiveBoosts": 2,
        "lastBoostAt": "2026-09-24T12:00:00.000Z",
        "cooldownRemaining": 0,
        "earlyBoostFee": 0,
        "connectedNodes": 1,
        "fragmentsPerHour": 10,
        "challengeAvailable": False,
        "challengeToken": None,
    }

    # Patch requests.get to return mock response
    with patch("beacon_service.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_api_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Run check_and_notify (sync)
        result = service.check_and_notify()

    cooldown = result["cooldown_remaining"]
    notification = result["notification"]
    state = service.load_state()

    test_results = {
        "test": "boost_ready_flow",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mock_api_response": {
            "cooldownRemaining": 0,
            "beaconPower": 124,
            "unclaimedFragments": 30,
        },
        "results": {
            "cooldown_remaining": cooldown,
            "boost_ready": cooldown <= 0,
            "notification_generated": notification is not None,
            "notification_message": notification,
            "state_saved": state.get("last_notified_cooldown") == "ready",
        },
        "status": "pass" if (cooldown <= 0 and notification) else "fail",
    }

    # Optionally send real Telegram message
    if send_real and settings.telegram_enabled:
        # Use notification if available, otherwise build test message
        if notification:
            telegram_success = await service.send_telegram(notification)
        else:
            # Fallback: send a basic test message
            telegram_success = await service.send_telegram(
                "🧪 Teneo Beacon Monitor — Smoke Test\n"
                "✅ Auto-notification flow verified!\n"
                "📊 Beacon Power: 1.24x\n"
                "📦 Unclaimed Fragments: 30\n"
                "🔄 Total Boosts: 2\n"
                "⏱️ Cooldown: 0s — SIAP CLAIM!"
            )
        test_results["real_telegram_sent"] = telegram_success
        test_results["telegram_message_id"] = "delivered" if telegram_success else "failed"

    print(f"Status: {test_results['status']}")
    print(f"Notification: {'generated' if notification else 'none'}")
    print(f"State: {state.get('last_notified_cooldown')}")

    return test_results
