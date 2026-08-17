#!/bin/bash
# Start both memward servers and process any pending backlog on startup.
set -e
cd "$(dirname "$0")"
source .env

echo "[memward] Starting processor on :8010..."
PYTHONPATH=src uv run uvicorn processor.main:app --port 8010 --reload &
PROCESSOR_PID=$!

echo "[memward] Starting core API on :8000..."
PYTHONPATH=src uv run uvicorn core.main:app --port 8000 --reload &
CORE_PID=$!

# Wait for both servers to be ready then drain any pending backlog
echo "[memward] Waiting for servers to be ready..."
sleep 4
curl -s -X POST "http://127.0.0.1:8010/process-pending?limit=50" > /dev/null && echo "[memward] Backlog drained."

echo "[memward] Both servers running. Press Ctrl+C to stop."
trap "kill $PROCESSOR_PID $CORE_PID 2>/dev/null" EXIT
wait
