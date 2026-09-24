#!/bin/bash
# Start Teneo Beacon Monitor — FastAPI server
cd "$(dirname "$0")"
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8765 --log-level info
