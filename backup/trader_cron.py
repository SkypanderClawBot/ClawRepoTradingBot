#!/usr/bin/env python3
"""
Botti Trader Cron - Exakt stündliche Reports
Läuft jede Stunde :00 und sendet Report
"""

import schedule
import time
import subprocess
from datetime import datetime
from pathlib import Path

def run_trader_with_report():
    """Trader ausführen und Report senden"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"[{now}] Stündlicher Trade-Scan...")
    
    try:
        # Trader ausführen
        result = subprocess.run(
            ["python3", "/data/.openclaw/workspace/botti_trader.py"],
            capture_output=True,
            text=True,
            cwd="/data/.openclaw/workspace",
            timeout=120
        )
        
        # Log speichern
        log_file = Path("/data/.openclaw/workspace/trading_data/cron.log")
        with open(log_file, "a") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Cron Run: {now}\n")
            f.write(f"{'='*60}\n")
            f.write(result.stdout)
        
        print(f"[{now}] Report gesendet.")
        
    except Exception as e:
        print(f"[{now}] Fehler: {e}")

# Jede Stunde :00 ausführen
schedule.every().hour.at(":00").do(run_trader_with_report)

print("="*60)
print("Botti Trader Cron gestartet")
print("Läuft jede Stunde :00 (08:00-22:00)")
print("Drücke Ctrl+C zum Beenden")
print("="*60)

# Ersten Lauf sofort machen
run_trader_with_report()

# Scheduler-Loop
while True:
    schedule.run_pending()
    time.sleep(30)  # Jede halbe Minute prüfen
