#!/usr/bin/env python3
"""
Botti Trader Bot 2 - Breakout Strategie
======================================
Komplett isoliert von Bot 1 (v4.0)
"""

import json
from pathlib import Path

CONFIG_BOT2 = {
    "name": "Breakout-Bot",
    "symbols": ["BTC-USD", "ETH-USD", "SOL-USD"],  # Nur Crypto
    "strategy": "breakout",  # Statt SMA-Crossover
    "entry": "high_20d_break",  # 20-Tage Hoch
    "stop_loss_pct": 0.03,  # 3% (enger)
    "take_profit_pct": 0.15,  # 15%
    "risk_per_trade": 0.02,  # 2% (höher)
    "data_dir": Path(__file__).parent / "trading_data_bot2",  # ISOLIERT
    "port": 7498,  # Anderer IBKR Port
}

# Eigener Portfolio-File
trading_data_bot2/portfolio.json
trading_data_bot2/reports/
trading_data_bot2/logs/
