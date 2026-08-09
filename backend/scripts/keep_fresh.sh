#!/usr/bin/env bash
# Keep FloodGuard forecast data fresh by running run_ingest.py every 10 min.
# Started as a daemon; logs to /tmp/floodguard_ingest.log.
set -u
cd "$(dirname "$0")/.."
source venv/bin/activate
# Force live ingest sources (Open-Meteo forecast + AWS, RainViewer radar) so
# the loop never silently drops back to mock fixtures.
export INGEST_MOCK=False
export FORECAST_LIVE=True
export AWS_LIVE=True
export RADAR_LIVE=True
while true; do
  echo "[$(date '+%F %T')] refresh cycle start" >> /tmp/floodguard_ingest.log
  python run_ingest.py >> /tmp/floodguard_ingest.log 2>&1 || true
  sleep 600
done
