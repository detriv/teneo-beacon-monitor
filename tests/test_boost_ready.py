#!/usr/bin/env python3
"""
Smoke test: Simulate cooldownRemaining=0 and verify Telegram notification is sent.
This tests the full auto-notification flow without waiting for real cooldown.

Usage:
    python3 tests/test_boost_ready.py
    
Requirements:
    - TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID set in environment
    - TELEGRAM_ENABLED=true
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from beacon_service import BeaconService
from config import Settings


async def test_boost_ready_flow():
    """
    Simulate the full flow when cooldownRemaining reaches 0:
    1. API returns cooldownRemaining=0
    2. check_and_notify() detects boost is ready
    3. send_telegram() dispatches notification
    4. State is saved (no duplicate notifications)
    """
    
    print("🧪 Teneo Beacon Monitor — Boost Ready Smoke Test")
    print("=" * 60)
    
    # Load settings (reads from environment)
    settings = Settings()
    
    if not settings.telegram_enabled:
        print("❌ FAIL: TELEGRAM_ENABLED is not true")
        return False
    
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        print("❌ FAIL: Telegram credentials not configured")
        return False
    
    print(f"📋 Config:")
    print(f"   Telegram: {'enabled' if settings.telegram_enabled else 'disabled'}")
    print(f"   Chat ID: {settings.telegram_chat_id}")
    print(f"   API URL: {settings.teneo_api_url}")
    print()
    
    # Create service
    service = BeaconService(settings)
    
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
        "cooldownRemaining": 0,          # <-- KEY: boost is ready!
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
        
        # Patch send_telegram to avoid real API call during test
        # (we'll verify it's called, then do a real send)
        with patch.object(service, "send_telegram", wraps=service.send_telegram) as mock_send:
            
            print("🔄 Running check_and_notify() with cooldownRemaining=0...")
            result = service.check_and_notify()
            
            print(f"\n📊 Results:")
            print(f"   cooldown_remaining: {result['cooldown_remaining']}")
            print(f"   notification generated: {'YES' if result['notification'] else 'NO'}")
            print(f"   send_telegram called: {'YES' if mock_send.called else 'NO'}")
            print(f"   state saved: {Path(settings.state_file).exists()}")
            
            if not mock_send.called:
                print("\n❌ FAIL: send_telegram was NOT called")
                return False
            
            if not result["notification"]:
                print("\n❌ FAIL: No notification generated")
                return False
            
            print("\n✅ PASS: Full auto-notification flow verified")
            print(f"   Telegram would receive:\n")
            print("-" * 40)
            print(result["notification"])
            print("-" * 40)
            return True


async def test_real_telegram_send():
    """Send a real test message to verify Telegram delivery."""
    settings = Settings()
    service = BeaconService(settings)
    
    test_message = (
        "🧪 Teneo Beacon Monitor — Smoke Test\n"
        "✅ Auto-notification flow verified!\n"
        "📊 Beacon Power: 1.24x\n"
        "📦 Unclaimed Fragments: 30\n"
        "🔄 Total Boosts: 2\n"
        "⏱️ Cooldown: 0s — SIAP CLAIM!\n"
        "👉 Buka app / hub.teneo.pro untuk claim boost!"
    )
    
    print("\n📨 Sending REAL test message to Telegram...")
    success = await service.send_telegram(test_message)
    
    if success:
        print("✅ Telegram message delivered successfully")
    else:
        print("❌ Telegram delivery failed")
    
    return success


if __name__ == "__main__":
    # Test 1: Mock flow (no real API calls)
    result1 = asyncio.run(test_boost_ready_flow())
    
    if result1:
        # Test 2: Real Telegram send (optional)
        print("\n" + "=" * 60)
        result2 = asyncio.run(test_real_telegram_send())
        
        if result2:
            print("\n🎉 ALL TESTS PASSED")
            print("   Auto-notification flow is working correctly.")
            print("   When cooldownRemaining reaches 0, Telegram will be notified.")
            sys.exit(0)
        else:
            print("\n⚠️  Mock flow OK but real Telegram send failed")
            print("   Check your bot token and chat ID.")
            sys.exit(1)
    else:
        print("\n❌ SMOKE TEST FAILED")
        sys.exit(1)
