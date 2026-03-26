#!/usr/bin/env python3
"""
Botti Trader - Virtueller Trading Bot v2.0 (Optimiert)
=====================================================
Autonomer Trading-Agent fuer Paper Trading mit Yahoo Finance Daten.

NEU in v2.0:
- Trailing Stop Loss (passt sich Gewinnen an)
- Trend-Filter (nur traden in Bull-Maerkten)
- Partielle Gewinnmitnahme (50% bei +20%, Rest mit Trailing Stop)
- Dynamische Positionsgroessen
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import yfinance as yf
import pandas as pd
import numpy as np

# Konfiguration v2.0
CONFIG = {
    "symbols": ["AAPL", "TSLA", "NVDA"],
    "currency": "EUR",
    "initial_capital": 1000.0,
    "sma_short": 20,
    "sma_long": 50,
    "stop_loss_pct": 0.05,        # -5% Initial
    "trailing_stop_pct": 0.10,    # -10% vom Hoch
    "partial_profit_pct": 0.20,   # +20% fuer erste 50%
    "trend_filter": True,         # Nur in Bull-Trends traden
    "max_position_pct": 0.40,     # Erhoeht auf 40%
    "data_dir": Path(__file__).parent / "trading_data",
    "portfolio_file": Path(__file__).parent / "trading_data" / "portfolio.json",
}


class Portfolio:
    """Virtuelles Portfolio Management v2.0"""
    
    def __init__(self, config: dict):
        self.config = config
        self.data_dir = config["data_dir"]
        self.data_dir.mkdir(exist_ok=True)
        self.portfolio = self._load_portfolio()
        
    def _load_portfolio(self) -> dict:
        """Portfolio laden oder initialisieren (inkl. Migration von v1.0)"""
        if self.config["portfolio_file"].exists():
            with open(self.config["portfolio_file"], "r") as f:
                portfolio = json.load(f)
                # Migration: neue Felder hinzufuegen falls nicht vorhanden
                for symbol, pos in portfolio.get("positions", {}).items():
                    if "highest_price" not in pos:
                        pos["highest_price"] = pos.get("entry_price", 0)
                    if "trailing_stop" not in pos:
                        pos["trailing_stop"] = pos.get("stop_loss", 0)
                    if "partial_sold" not in pos:
                        pos["partial_sold"] = False
                return portfolio
        
        return {
            "cash": self.config["initial_capital"],
            "initial_capital": self.config["initial_capital"],
            "positions": {},
            "trade_history": [],
            "version": "2.0",
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
        }
    
    def save(self):
        """Portfolio speichern"""
        self.portfolio["last_updated"] = datetime.now().isoformat()
        with open(self.config["portfolio_file"], "w") as f:
            json.dump(self.portfolio, f, indent=2)
    
    def has_position(self, symbol: str) -> bool:
        """Pruefen ob Position besteht"""
        return symbol in self.portfolio["positions"]
    
    def get_position(self, symbol: str) -> Optional[dict]:
        """Position abrufen"""
        return self.portfolio["positions"].get(symbol)
    
    def buy(self, symbol: str, price: float, shares: int, reason: str = "") -> dict:
        """Virtueller Kauf"""
        cost = price * shares
        
        if cost > self.portfolio["cash"]:
            return {"success": False, "error": "Nicht genug Cash"}
        
        position = {
            "symbol": symbol,
            "entry_price": price,
            "shares": shares,
            "original_shares": shares,
            "entry_date": datetime.now().isoformat(),
            "cost_basis": cost,
            "current_price": price,
            "highest_price": price,           # Fuer Trailing Stop
            "stop_loss": price * (1 - self.config["stop_loss_pct"]),
            "trailing_stop": price * (1 - self.config["trailing_stop_pct"]),
            "partial_sold": False,
            "reason": reason,
        }
        
        self.portfolio["positions"][symbol] = position
        self.portfolio["cash"] -= cost
        
        trade = {
            "id": len(self.portfolio["trade_history"]) + 1,
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "action": "BUY",
            "price": price,
            "shares": shares,
            "total": cost,
            "reason": reason,
            "cash_after": self.portfolio["cash"],
        }
        self.portfolio["trade_history"].append(trade)
        self.save()
        
        return {"success": True, "trade": trade, "position": position}
    
    def sell(self, symbol: str, price: float, shares: int, reason: str = "") -> dict:
        """Virtueller Verkauf (teilweise oder vollstaendig)"""
        position = self.portfolio["positions"].get(symbol)
        if not position:
            return {"success": False, "error": f"Keine Position fuer {symbol}"}
        
        if shares > position["shares"]:
            shares = position["shares"]
        
        proceeds = price * shares
        cost_basis_per_share = position["cost_basis"] / position["original_shares"]
        cost_for_shares = cost_basis_per_share * shares
        
        pnl = proceeds - cost_for_shares
        pnl_pct = (pnl / cost_for_shares) * 100 if cost_for_shares > 0 else 0
        
        # Trade loggen
        trade = {
            "id": len(self.portfolio["trade_history"]) + 1,
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "action": "SELL_PARTIAL" if shares < position["shares"] else "SELL",
            "price": price,
            "shares": shares,
            "total": proceeds,
            "entry_price": position["entry_price"],
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "reason": reason,
            "cash_after": self.portfolio["cash"] + proceeds,
        }
        self.portfolio["trade_history"].append(trade)
        
        # Position aktualisieren
        position["shares"] -= shares
        position["cost_basis"] -= cost_for_shares
        
        if position["shares"] <= 0:
            del self.portfolio["positions"][symbol]
        
        self.portfolio["cash"] += proceeds
        self.save()
        
        return {
            "success": True,
            "trade": trade,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "remaining_shares": position.get("shares", 0)
        }
    
    def update_prices(self, prices: dict):
        """Preise aktualisieren und Trailing Stops anpassen"""
        for symbol, price in prices.items():
            if symbol in self.portfolio["positions"]:
                pos = self.portfolio["positions"][symbol]
                pos["current_price"] = price
                
                # Highest Price aktualisieren
                if price > pos["highest_price"]:
                    pos["highest_price"] = price
                    # Trailing Stop nachziehen
                    new_trailing = price * (1 - self.config["trailing_stop_pct"])
                    if new_trailing > pos["trailing_stop"]:
                        pos["trailing_stop"] = new_trailing
    
    def check_exit_signals(self, prices: dict) -> List[dict]:
        """Alle Exit-Signale pruefen (Stop-Loss, Trailing, Partial Profit)"""
        signals = []
        
        for symbol, position in self.portfolio["positions"].items():
            current_price = prices.get(symbol)
            if not current_price:
                continue
            
            entry = position["entry_price"]
            
            # 1. Partial Profit (50% bei +20%) - nur wenn noch nicht verkauft
            if not position.get("partial_sold", False):
                target_price = entry * (1 + self.config["partial_profit_pct"])
                if current_price >= target_price:
                    shares_to_sell = position["shares"] // 2  # 50%
                    if shares_to_sell > 0:
                        signals.append({
                            "symbol": symbol,
                            "action": "SELL_PARTIAL",
                            "shares": shares_to_sell,
                            "reason": f"Partial Profit (+{self.config['partial_profit_pct']*100:.0f}%)",
                            "price": current_price,
                        })
                        position["partial_sold"] = True
                        continue
            
            # 2. Trailing Stop (nur wenn Partial Profit erreicht wurde oder ohnehin aktiv)
            if current_price <= position.get("trailing_stop", position["stop_loss"]):
                signals.append({
                    "symbol": symbol,
                    "action": "SELL",
                    "shares": position["shares"],  # Alle restlichen
                    "reason": f"Trailing Stop ({self.config['trailing_stop_pct']*100:.0f}% vom Hoch)",
                    "price": current_price,
                })
                continue
            
            # 3. Initial Stop-Loss (nur wenn noch kein Trailing aktiv)
            if current_price <= position["stop_loss"]:
                signals.append({
                    "symbol": symbol,
                    "action": "SELL",
                    "shares": position["shares"],
                    "reason": f"Stop-Loss ({self.config['stop_loss_pct']*100:.0f}%)",
                    "price": current_price,
                })
        
        return signals
    
    def get_portfolio_value(self, prices: dict) -> dict:
        """Gesamtwert berechnen"""
        positions_value = 0.0
        positions_details = []
        
        for symbol, position in self.portfolio["positions"].items():
            current_price = prices.get(symbol, position["current_price"])
            value = current_price * position["shares"]
            
            # Realisierte PnL von Partial Sales
            realized_pnl = sum(
                t.get("pnl", 0) for t in self.portfolio["trade_history"]
                if t["symbol"] == symbol and t["action"] == "SELL_PARTIAL"
            )
            
            # Unrealisierte PnL
            unrealized_pnl = value - position["cost_basis"]
            total_pnl = realized_pnl + unrealized_pnl
            total_pnl_pct = (total_pnl / (position["cost_basis"] + realized_pnl)) * 100 if position["cost_basis"] > 0 else 0
            
            positions_value += value
            positions_details.append({
                "symbol": symbol,
                "shares": position["shares"],
                "original_shares": position["original_shares"],
                "entry": position["entry_price"],
                "current": current_price,
                "highest": position["highest_price"],
                "trailing_stop": position.get("trailing_stop", position["stop_loss"]),
                "value": value,
                "pnl": total_pnl,
                "pnl_pct": total_pnl_pct,
                "partial_sold": position.get("partial_sold", False),
            })
        
        total_value = self.portfolio["cash"] + positions_value
        total_return = total_value - self.portfolio["initial_capital"]
        total_return_pct = (total_return / self.portfolio["initial_capital"]) * 100
        
        return {
            "cash": self.portfolio["cash"],
            "positions_value": positions_value,
            "total_value": total_value,
            "total_return": total_return,
            "total_return_pct": total_return_pct,
            "positions": positions_details,
        }


class Strategy:
    """Optimierte SMA + Trend-Filter Strategie"""
    
    def __init__(self, config: dict):
        self.config = config
    
    def analyze(self, symbol: str, data: pd.DataFrame) -> dict:
        """Strategie-Analyse mit Trend-Filter"""
        if len(data) < self.config["sma_long"]:
            return {"signal": "HOLD", "reason": "Nicht genug Daten"}
        
        # Indikatoren
        data["SMA20"] = data["Close"].rolling(window=self.config["sma_short"]).mean()
        data["SMA50"] = data["Close"].rolling(window=self.config["sma_long"]).mean()
        data["RSI"] = self._calculate_rsi(data["Close"])
        
        # Letzte Werte
        last = data.iloc[-1]
        prev = data.iloc[-2]
        
        current_price = last["Close"]
        sma20 = last["SMA20"]
        sma50 = last["SMA50"]
        prev_sma20 = prev["SMA20"]
        prev_sma50 = prev["SMA50"]
        
        # Trend-Bedingungen
        in_uptrend = sma20 > sma50  # Bull-Trend
        price_above_sma20 = current_price > sma20
        golden_cross = prev_sma20 <= prev_sma50 and sma20 > sma50
        death_cross = prev_sma20 >= prev_sma50 and sma20 < sma50
        
        # Volumen
        avg_vol = data["Volume"].rolling(20).mean().iloc[-1]
        vol_spike = last["Volume"] > avg_vol * 1.2
        
        # RSI Filter (nicht überkauft/überverkauft)
        rsi_ok = 30 < last["RSI"] < 70
        
        # BUY Signal
        if golden_cross:
            if self.config["trend_filter"] and not in_uptrend:
                return {"signal": "HOLD", "reason": "Golden Cross aber kein Uptrend"}
            
            strength = 0.6
            reasons = ["Golden Cross"]
            
            if price_above_sma20:
                strength += 0.1
                reasons.append("Price>SMA20")
            if vol_spike:
                strength += 0.15
                reasons.append("Volume+20%")
            if rsi_ok:
                strength += 0.15
                reasons.append("RSI OK")
            
            return {
                "signal": "BUY",
                "confidence": strength,
                "reason": " + ".join(reasons),
                "indicators": {
                    "close": current_price,
                    "sma20": sma20,
                    "sma50": sma50,
                    "rsi": last["RSI"],
                    "uptrend": in_uptrend,
                }
            }
        
        # SELL Signal (nur fuer Bestandsexit)
        if death_cross:
            return {
                "signal": "SELL",
                "confidence": 0.7,
                "reason": "Death Cross",
                "indicators": {"close": current_price, "sma20": sma20, "sma50": sma50}
            }
        
        return {"signal": "HOLD", "reason": "", "indicators": {"close": current_price}}
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """RSI berechnen"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def calculate_position_size(self, portfolio: Portfolio, price: float) -> int:
        """Dynamische Positionsgroesse"""
        available_cash = portfolio.portfolio["cash"]
        max_investment = available_cash * self.config["max_position_pct"]
        
        if max_investment < price:
            return 0
        
        # Mind. 100 Euro investieren
        if max_investment < 100:
            return 0
        
        return int(max_investment / price)


class BottiTrader:
    """Haupt-Trading-Klasse v2.0"""
    
    def __init__(self, config: dict = None):
        self.config = config or CONFIG
        self.portfolio = Portfolio(self.config)
        self.strategy = Strategy(self.config)
        self.reports_dir = self.config["data_dir"] / "reports"
        self.reports_dir.mkdir(exist_ok=True)
    
    def fetch_data(self, symbol: str, period: str = "3mo") -> pd.DataFrame:
        """Daten laden"""
        ticker = yf.Ticker(symbol)
        return ticker.history(period=period)
    
    def fetch_current_prices(self) -> dict:
        """Aktuelle Preise"""
        prices = {}
        for symbol in self.config["symbols"]:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1d")
                if not hist.empty:
                    prices[symbol] = hist["Close"].iloc[-1]
            except Exception as e:
                print(f"Fehler beim Laden von {symbol}: {e}")
        return prices
    
    def run_daily_analysis(self) -> dict:
        """Taegliche Analyse"""
        print(f"\n{'='*70}")
        print(f"BOTTI TRADER v2.0 - Taegliche Analyse")
        print(f"Zeit: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")
        
        print("Strategie: SMA Crossover + Trailing Stops + Partial Profit")
        print(f"Config: SL={self.config['stop_loss_pct']*100:.0f}%, "
              f"Trailing={self.config['trailing_stop_pct']*100:.0f}%, "
              f"Partial={self.config['partial_profit_pct']*100:.0f}%\n")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "signals": [],
            "executed_trades": [],
            "portfolio_value": None,
        }
        
        # Preise laden
        current_prices = self.fetch_current_prices()
        print("Aktuelle Preise:")
        for symbol, price in current_prices.items():
            print(f"   {symbol}: ${price:.2f}")
        print()
        
        # Portfolio updaten
        self.portfolio.update_prices(current_prices)
        
        # Exit-Signale pruefen
        exit_signals = self.portfolio.check_exit_signals(current_prices)
        for signal in exit_signals:
            print(f"EXIT-SIGNAL: {signal['symbol']} - {signal['reason']}")
            result = self.portfolio.sell(
                signal["symbol"],
                signal["price"],
                signal["shares"],
                signal["reason"]
            )
            if result["success"]:
                print(f"   VERKAUFT {result['trade']['shares']} shares! "
                      f"P&L: EUR {result['pnl']:.2f} ({result['pnl_pct']:+.2f}%)")
                if result.get('remaining_shares', 0) > 0:
                    print(f"   Verbleibend: {result['remaining_shares']} shares")
                results["executed_trades"].append(result)
            else:
                print(f"   Fehler: {result['error']}")
        
        # Neue Signale
        for symbol in self.config["symbols"]:
            print(f"\nAnalysiere {symbol}...")
            
            try:
                data = self.fetch_data(symbol, period="3mo")
                analysis = self.strategy.analyze(symbol, data)
                
                print(f"   Signal: {analysis['signal']}")
                if analysis.get('reason'):
                    print(f"   Grund: {analysis['reason']}")
                
                ind = analysis.get('indicators', {})
                print(f"   Preis: ${ind.get('close', 0):.2f}, "
                      f"SMA20: ${ind.get('sma20', 0):.2f}, "
                      f"SMA50: ${ind.get('sma50', 0):.2f}")
                
                results["signals"].append({"symbol": symbol, **analysis})
                
                # BUY
                if analysis["signal"] == "BUY" and not self.portfolio.has_position(symbol):
                    shares = self.strategy.calculate_position_size(
                        self.portfolio, ind.get('close', 0)
                    )
                    if shares > 0:
                        result = self.portfolio.buy(
                            symbol, ind.get('close', 0), shares, analysis["reason"]
                        )
                        if result["success"]:
                            print(f"   GEKAUFT: {shares} shares @ ${ind.get('close', 0):.2f}")
                            results["executed_trades"].append(result)
                        else:
                            print(f"   Fehler: {result['error']}")
                    else:
                        print(f"   Zu wenig Cash fuer Mindestposition")
                
                # SELL (Strategie-basiert)
                elif analysis["signal"] == "SELL" and self.portfolio.has_position(symbol):
                    pos = self.portfolio.get_position(symbol)
                    result = self.portfolio.sell(
                        symbol, ind.get('close', 0), pos["shares"], analysis["reason"]
                    )
                    if result["success"]:
                        print(f"   STRATEGIE-EXIT: P&L EUR {result['pnl']:.2f}")
                        results["executed_trades"].append(result)
                
                else:
                    print(f"   Keine Aktion")
                    
            except Exception as e:
                print(f"   Fehler: {e}")
        
        # Portfolio-Value
        portfolio_value = self.portfolio.get_portfolio_value(current_prices)
        results["portfolio_value"] = portfolio_value
        
        # Report
        self._generate_report(results)
        
        return results
    
    def _generate_report(self, results: dict):
        """Report erstellen"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        report_file = self.reports_dir / f"report_{date_str}.txt"
        
        pv = results["portfolio_value"]
        
        report = f"""
{'='*70}
              BOTTI TRADER v2.0 - REPORT
{'='*70}
Datum: {datetime.now().strftime('%Y-%m-%d %H:%M')}

PORTFOLIO
---------
Cash:           EUR {pv['cash']:>10.2f}
Positionen:     EUR {pv['positions_value']:>10.2f}
Gesamtwert:     EUR {pv['total_value']:>10.2f}
Performance:    EUR {pv['total_return']:>+10.2f} ({pv['total_return_pct']:+.2f}%)

OFFENE POSITIONEN
-----------------
"""
        
        if pv["positions"]:
            for pos in pv["positions"]:
                report += f"""
   {pos['symbol']} - {pos['shares']}/{pos['original_shares']} shares
   Entry: {pos['entry']:.2f} | Current: {pos['current']:.2f} | High: {pos['highest']:.2f}
   Trailing Stop: {pos['trailing_stop']:.2f} | P&L: {pos['pnl']:.2f} ({pos['pnl_pct']:+.2f}%)
   Partial Sold: {'Ja' if pos['partial_sold'] else 'Nein'}
"""
        else:
            report += "   Keine offenen Positionen\n"
        
        report += f"""

SIGNALE HEUTE
-------------
"""
        for sig in results["signals"]:
            report += f"   {sig['symbol']}: {sig['signal']}"
            if sig.get('reason'):
                report += f" ({sig['reason']})"
            report += "\n"
        
        report += """

TRADES HEUTE
-------------
"""
        if results["executed_trades"]:
            for trade in results["executed_trades"]:
                t = trade["trade"]
                report += f"""
   #{t['id']}: {t['action']} {t['symbol']}
   Preis: {t['price']:.2f} | Shares: {t['shares']} | Total: {t['total']:.2f}
   P&L: {t.get('pnl', 0):+.2f} | Grund: {t['reason']}
"""
        else:
            report += "   Keine Trades\n"
        
        report += "\n" + "="*70 + "\n"
        
        with open(report_file, "w") as f:
            f.write(report)
        
        print(f"\nReport gespeichert: {report_file}")
        print(report)
    
    def get_summary(self) -> str:
        """Kurze Zusammenfassung"""
        current_prices = self.fetch_current_prices()
        pv = self.portfolio.get_portfolio_value(current_prices)
        
        msg = f"""Botti Trader v2.0 Update

Gesamtwert: EUR {pv['total_value']:.2f}
Performance: {pv['total_return_pct']:+.2f}%
Cash: EUR {pv['cash']:.2f}
Positionen: {len(pv['positions'])}

Strategie: SMA + Trailing Stop + Partial Profit"""
        
        if pv["positions"]:
            msg += "\n\nOffene Positionen:\n"
            for pos in pv["positions"]:
                msg += f"- {pos['symbol']}: {pos['shares']}/{pos['original_shares']} sh, "
                msg += f"P&L {pos['pnl_pct']:+.1f}%"
                if pos['partial_sold']:
                    msg += " (Partial)"
                msg += "\n"
        
        return msg


def main():
    """Hauptfunktion"""
    trader = BottiTrader()
    results = trader.run_daily_analysis()
    return trader.get_summary()


if __name__ == "__main__":
    summary = main()
    print("\nTelegram Summary:")
    print(summary)
