#!/usr/bin/env python3
"""
Botti Trader Scheduler
Läuft im Hintergrund und führt den Trader täglich aus.
"""

import schedule
import time
import subprocess
from datetime import datetime
from pathlib import Path

def run_trader():
    """Trader ausführen und Log erstellen"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] Starte Botti Trader...")
    
    try:
        result = subprocess.run(
            ["python3", "/data/.openclaw/workspace/botti_trader.py"],
            capture_output=True,
            text=True,
            cwd="/data/.openclaw/workspace"
        )
        
        # Log speichern
        log_file = Path("/data/.openclaw/workspace/trading_data/scheduler.log")
        with open(log_file, "a") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Run: {now}\n")
            f.write(f"{'='*60}\n")
            f.write(result.stdout)
            if result.stderr:
                f.write("\nERRORS:\n")
                f.write(result.stderr)
        
        print(f"[{now}] Trader abgeschlossen.")
        
    except Exception as e:
        print(f"[{now}] Fehler: {e}")

def run_now():
    """Sofort ausführen"""
    run_trader()

# Schedule einrichten
# Täglich um 09:00 (nach US Marktöffnung)
schedule.every().day.at("09:00").do(run_trader)

# Optional: Auch um 21:00 (nach US Marktschluss)
schedule.every().day.at("21:00").do(run_trader)

print("=" * 60)
print("Botti Trader Scheduler gestartet")
print("Läuft täglich um 09:00 und 21:00 Uhr")
print("Drücke Ctrl+C zum Beenden")
print("=" * 60)

# Ersten Lauf direkt machen
print("\nErster Lauf (Test)...")
run_now()

# Scheduler-Loop
while True:
    schedule.run_pending()
    time.sleep(60)  # Jede Minute prüfen
