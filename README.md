# Teneo Beacon Monitor

FastAPI service that monitors your Teneo Protocol Beacon boost cooldown and notifies you when it's ready to claim.

## Features

- ✅ Auto-check boost cooldown every hour
- ✅ REST API: `/status`, `/check`, `/health`, `/notify`
- ✅ Webhook support (Discord/Telegram/custom)
- ✅ APScheduler background job
- ✅ State persistence (no duplicate notifications)
- ✅ Docker-ready

## Quick Start

```bash
# 1. Clone / copy project
cd teneo-beacon-monitor

# 2. Setup venv
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Configure auth token
mkdir -p ~/.config/teneo-beacon
echo 'TENEO_AUTH_TOKEN=<your_token>' > ~/.config/teneo-beacon/bot.env
chmod 600 ~/.config/teneo-beacon/bot.env

# 4. Run
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8765
```

## API Endpoints

| Endpoint | Method | Description |
|:--|:--|:--|
| `/` | GET | Service info |
| `/health` | GET | Health check |
| `/status` | GET | Current beacon status from Teneo API |
| `/check` | POST | Trigger manual cooldown check |
| `/notify` | GET | Last ready notification (text) |

## Configuration

Environment variables (or `bot.env`):

| Variable | Default | Description |
|:--|:--|:--|
| `TENEO_AUTH_TOKEN` | — | Bearer token from hub.teneo.pro |
| `TENEO_API_URL` | `https://gateway.teneo.pro/api/user/beacon` | API endpoint |
| `CHECK_INTERVAL_SECONDS` | `3600` | Check interval (1 hour) |
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | — | Your Telegram chat ID |
| `TELEGRAM_ENABLED` | `false` | Enable Telegram notifications |
| `WEBHOOK_URL` | — | External webhook for notifications |
| `WEBHOOK_ENABLED` | `false` | Enable webhook delivery |
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8765` | Server port |

## Telegram Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) → get `TELEGRAM_BOT_TOKEN`
2. Get your chat ID: message `@userinfobot` or use `https://t.me/getmyid_bot`
3. Add to `~/.config/teneo-beacon/bot.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
   TELEGRAM_CHAT_ID=123456789
   TELEGRAM_ENABLED=true
   ```
4. Restart the monitor — notifications will be sent when boost is ready

## Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8765"]
```

## systemd (auto-start)

```ini
# ~/.config/systemd/user/teneo-monitor.service
[Unit]
Description=Teneo Beacon Monitor
After=network-online.target

[Service]
ExecStart=/home/deva/teneo-beacon-monitor/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8765
WorkingDirectory=/home/deva/teneo-beacon-monitor
Restart=always

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable teneo-monitor
systemctl --user start teneo-monitor
```
