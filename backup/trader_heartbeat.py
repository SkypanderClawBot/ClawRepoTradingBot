#!/usr/bin/env python3
"""
Botti Trader - Heartbeat Runner
Wird bei jedem Heartbeat aufgerufen.
"""

import sys
sys.path.insert(0, '/data/.openclaw/workspace')

from trader_daemon import should_run, run_trader

def check_and_run():
    """Prüft ob der Trader laufen soll und führt ihn aus"""
    if should_run():
        print("[Heartbeat] Trading-Zeit erkannt! Starte Botti Trader...")
        success = run_trader()
        return success
    else:
        print("[Heartbeat] Keine Trading-Zeit. Warte auf 09:00 oder 21:00...")
        return None

if __name__ == "__main__":
    result = check_and_run()
    sys.exit(0 if result in [True, None] else 1)
