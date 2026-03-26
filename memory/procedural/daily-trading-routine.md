# Tägliche Trading Routine

## Morgens (08:00-09:00)
1. **VIX Check:** <25 = trade, >25 = pause
2. **Pre-Market Scan:** Keine Trades (US Markt noch zu)
3. **08:00 First Scan:** Portfolio checken

## Handelszeit (09:30-22:00 US / 15:30-04:00 DE)
1. **Stündlicher Scan:** Alle Assets durchlaufen
2. **Signal Check:** ML + Regime + SMA Cross
3. **Order Placement:** 1% Risk Sizing
4. **Trailing Update:** Höchststände tracken

## Abends (22:00-23:00)
1. **Letzter Scan:** 22:00
2. **Portfolio Check:** Offene Positionen
3. **23:00:** Memory Organizer laufen lassen

## Weekly (Sonntags)
1. **Backtest Review:** Performance analysieren
2. **Rebalance:** 10% Regel checken
3. **Earnings Update:** Termine für nächste Woche

## Emergency
- **VIX >30:** Sofort Verkauf aller Positionen
- **Regime Bear:** Keine neuen Trades
- **Trailing Hit:** Auto-Verkauf

## Kommunikation
- **Stündlich:** Report senden (auch bei HOLD)
- **Bei Trade:** Sofort Alert
- **Bei Fehler:** Loggen + MEMORY Regel vorschlagen
