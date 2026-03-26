#!/bin/bash
# Botti Trader - Daily Runner
# Wird vom Cron-Job aufgerufen

cd /data/.openclaw/workspace
python3 botti_trader.py > /data/.openclaw/workspace/trading_data/last_run.log 2>&1
