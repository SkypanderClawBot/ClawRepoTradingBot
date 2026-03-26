---
summary: "Daily trading bot + memory manager checks"
read_when:
  - Heartbeat polling
---

# HEARTBEAT.md - Botti Trader + Memory Manager Tasks

## Anweisung fuer Heartbeats

Bei jedem Heartbeat:
1. Pruefe die aktuelle Zeit
2. Fuehre aus: `python3 /data/.openclaw/workspace/trader_heartbeat.py` (stündlich Report senden)
3. Alle 2 Stunden: `bash /data/.openclaw/workspace/skills/memory-manager/detect.sh` (Memory Check)
4. Wenn WARN/CRITICAL: `bash /data/.openclaw/workspace/skills/memory-manager/snapshot.sh`
5. Täglich 23:00: `bash /data/.openclaw/workspace/skills/memory-manager/organize.sh`

## Trading Zeiten (mit stündlichen Reports)
- 08:00-22:00 - Stündlicher Scan + Report senden (auch wenn HOLD)
- 23:00 - Memory Organizer

## Letzte Laeufe
check memory/heartbeat-state.json fuer "lastRuns"

## Memory Manager
- Alle 2h: Compression Check
- Bei >70%: WARNING
- Bei >85%: CRITICAL + Snapshot
- 23:00: Automatische Organisation
