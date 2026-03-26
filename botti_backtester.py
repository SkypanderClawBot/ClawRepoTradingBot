#!/usr/bin/env python3
"""
Botti Backtester - Strategie-Test-Suite
=====================================
Testet Trading-Strategien auf historischen Daten.

Features:
- Walk-forward Backtesting
- Performance-Metriken (Sharpe, Drawdown, Winrate)
- Trade-Analysis
- Vergleich mit Buy-and-Hold
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
from collections import defaultdict

import yfinance as yf


@dataclass
class BacktestConfig:
    """Konfiguration fuer Backtest"""
    symbols: List[str]
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    initial_capital: float = 10000.0
    sma_short: int = 20
    sma_long: int = 50
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.10
    max_position_pct: float = 0.33
    

@dataclass
class Trade:
    """Einzelner Trade"""
    id: int
    symbol: str
    entry_date: datetime
    entry_price: float
    shares: int
    exit_date: datetime = None
    exit_price: float = None
    exit_reason: str = ""
    
    @property
    def pnl(self) -> float:
        if self.exit_price:
            return (self.exit_price - self.entry_price) * self.shares
        return 0.0
    
    @property
    def pnl_pct(self) -> float:
        if self.exit_price:
            return ((self.exit_price - self.entry_price) / self.entry_price) * 100
        return 0.0
    
    @property
    def is_open(self) -> bool:
        return self.exit_date is None
    
    @property
    def is_win(self) -> bool:
        return self.pnl > 0


class Strategy:
    """SMA Crossover Strategie mit mehr Indikatoren"""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Alle Indikatoren berechnen"""
        df = data.copy()
        
        # Gleitende Durchschnitte
        df['SMA20'] = df['Close'].rolling(window=self.config.sma_short).mean()
        df['SMA50'] = df['Close'].rolling(window=self.config.sma_long).mean()
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        ema12 = df['Close'].ewm(span=12).mean()
        ema26 = df['Close'].ewm(span=26).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        
        # Volumen-Durchschnitt
        df['Vol_SMA20'] = df['Volume'].rolling(window=20).mean()
        df['Vol_Ratio'] = df['Volume'] / df['Vol_SMA20']
        
        # Bollinger Bands
        df['BB_Middle'] = df['Close'].rolling(window=20).mean()
        bb_std = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
        df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
        df['BB_Position'] = (df['Close'] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])
        
        return df
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Signale generieren basierend auf mehreren Indikatoren"""
        df = self.calculate_indicators(data)
        
        # Signal-Spalten initialisieren
        df['Signal'] = 'HOLD'
        df['Signal_Reason'] = ''
        df['Signal_Strength'] = 0.0
        
        for i in range(1, len(df)):
            if pd.isna(df['SMA20'].iloc[i]) or pd.isna(df['SMA50'].iloc[i]):
                continue
            
            current = df.iloc[i]
            prev = df.iloc[i-1]
            
            # SMA Crossover
            golden_cross = prev['SMA20'] <= prev['SMA50'] and current['SMA20'] > current['SMA50']
            death_cross = prev['SMA20'] >= prev['SMA50'] and current['SMA20'] < current['SMA50']
            
            # Zusätzliche Checks
            rsi_ok = 30 < current['RSI'] < 70  # Nicht überkauft/überverkauft
            volume_spike = current['Vol_Ratio'] > 1.2
            macd_bullish = current['MACD'] > current['MACD_Signal']
            price_above_sma = current['Close'] > current['SMA20']
            
            # BUY Signal (Multi-Faktor)
            if golden_cross:
                strength = 0.5
                reasons = ["Golden Cross"]
                
                if volume_spike:
                    strength += 0.15
                    reasons.append("Volume Spike")
                if macd_bullish:
                    strength += 0.15
                    reasons.append("MACD Bullish")
                if price_above_sma:
                    strength += 0.1
                    reasons.append("Price > SMA20")
                if rsi_ok:
                    strength += 0.1
                    reasons.append("RSI OK")
                
                df.loc[df.index[i], 'Signal'] = 'BUY'
                df.loc[df.index[i], 'Signal_Reason'] = " + ".join(reasons)
                df.loc[df.index[i], 'Signal_Strength'] = strength
            
            # SELL Signal
            elif death_cross:
                strength = 0.5
                reasons = ["Death Cross"]
                
                if not macd_bullish:
                    strength += 0.2
                    reasons.append("MACD Bearish")
                
                df.loc[df.index[i], 'Signal'] = 'SELL'
                df.loc[df.index[i], 'Signal_Reason'] = " + ".join(reasons)
                df.loc[df.index[i], 'Signal_Strength'] = strength
        
        return df


class Backtester:
    """Haupt-Backtest-Klasse"""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.strategy = Strategy(config)
        self.trades: List[Trade] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        self.open_positions: Dict[str, Trade] = {}
        
    def fetch_data(self, symbol: str) -> pd.DataFrame:
        """Historische Daten laden"""
        ticker = yf.Ticker(symbol)
        data = ticker.history(start=self.config.start_date, end=self.config.end_date)
        return data
    
    def run(self) -> dict:
        """Backtest durchführen"""
        print(f"\n{'='*70}")
        print(f"BOTTI BACKTESTER")
        print(f"{'='*70}")
        print(f"Zeitraum: {self.config.start_date} bis {self.config.end_date}")
        print(f"Startkapital: EUR {self.config.initial_capital:,.2f}")
        print(f"Symbole: {', '.join(self.config.symbols)}")
        print(f"{'='*70}\n")
        
        # Daten laden und analysieren
        all_signals = []
        
        for symbol in self.config.symbols:
            print(f"Lade Daten fuer {symbol}...")
            data = self.fetch_data(symbol)
            
            if data.empty:
                print(f"  WARNUNG: Keine Daten fuer {symbol}")
                continue
            
            # Strategie anwenden
            analyzed = self.strategy.generate_signals(data)
            
            print(f"  Geladen: {len(data)} Tage")
            
            # Signale extrahieren
            signals = analyzed[analyzed['Signal'] != 'HOLD'].copy()
            for idx, row in signals.iterrows():
                all_signals.append({
                    'date': idx,
                    'symbol': symbol,
                    'signal': row['Signal'],
                    'price': row['Close'],
                    'reason': row['Signal_Reason'],
                    'strength': row['Signal_Strength'],
                    'data': row
                })
        
        # Nach Datum sortieren
        all_signals.sort(key=lambda x: x['date'])
        
        print(f"\nGefundene Signale: {len(all_signals)}")
        print(f"BUY: {sum(1 for s in all_signals if s['signal'] == 'BUY')}")
        print(f"SELL: {sum(1 for s in all_signals if s['signal'] == 'SELL')}")
        
        # Simulation durchlaufen
        cash = self.config.initial_capital
        daily_values = []
        
        print("\nSimuliere Trading...")
        
        # Alle Tage durchlaufen
        all_dates = set()
        for symbol in self.config.symbols:
            data = self.fetch_data(symbol)
            all_dates.update(data.index)
        
        all_dates = sorted(all_dates)
        
        for current_date in all_dates:
            # Tägliches Portfolio-Update
            day_value = cash
            
            for symbol, trade in list(self.open_positions.items()):
                try:
                    data = self.fetch_data(symbol)
                    if current_date in data.index:
                        current_price = data.loc[current_date, 'Close']
                        position_value = current_price * trade.shares
                        day_value += position_value
                        
                        # Stop-Loss / Take-Profit prüfen
                        if current_price <= trade.entry_price * (1 - self.config.stop_loss_pct):
                            # Stop-Loss ausgelöst
                            trade.exit_date = current_date
                            trade.exit_price = current_price
                            trade.exit_reason = f"Stop-Loss ({self.config.stop_loss_pct*100:.0f}%)"
                            cash += current_price * trade.shares
                            print(f"  {current_date.strftime('%Y-%m-%d')}: STOP-LOSS {symbol} @ ${current_price:.2f}")
                            del self.open_positions[symbol]
                            
                        elif current_price >= trade.entry_price * (1 + self.config.take_profit_pct):
                            # Take-Profit ausgelöst
                            trade.exit_date = current_date
                            trade.exit_price = current_price
                            trade.exit_reason = f"Take-Profit ({self.config.take_profit_pct*100:.0f}%)"
                            cash += current_price * trade.shares
                            print(f"  {current_date.strftime('%Y-%m-%d')}: TAKE-PROFIT {symbol} @ ${current_price:.2f}")
                            del self.open_positions[symbol]
                except:
                    pass
            
            daily_values.append((current_date, day_value))
            
            # Signale für diesen Tag verarbeiten
            day_signals = [s for s in all_signals if s['date'] == current_date]
            
            for signal in day_signals:
                if signal['signal'] == 'BUY' and signal['symbol'] not in self.open_positions:
                    # Kaufen
                    price = signal['price']
                    max_invest = cash * self.config.max_position_pct
                    shares = int(max_invest / price)
                    
                    if shares > 0:
                        cost = shares * price
                        cash -= cost
                        
                        trade = Trade(
                            id=len(self.trades) + 1,
                            symbol=signal['symbol'],
                            entry_date=current_date,
                            entry_price=price,
                            shares=shares
                        )
                        self.trades.append(trade)
                        self.open_positions[signal['symbol']] = trade
                        print(f"  {current_date.strftime('%Y-%m-%d')}: BUY {signal['symbol']} {shares} shares @ ${price:.2f}")
                
                elif signal['signal'] == 'SELL' and signal['symbol'] in self.open_positions:
                    # Verkaufen
                    trade = self.open_positions[signal['symbol']]
                    price = signal['price']
                    
                    trade.exit_date = current_date
                    trade.exit_price = price
                    trade.exit_reason = signal['reason']
                    
                    cash += price * trade.shares
                    del self.open_positions[signal['symbol']]
                    print(f"  {current_date.strftime('%Y-%m-%d')}: SELL {signal['symbol']} {trade.shares} shares @ ${price:.2f} (PnL: {trade.pnl_pct:+.2f}%)")
        
        # Offene Positionen am Ende schliessen
        final_date = all_dates[-1] if all_dates else datetime.now()
        for symbol, trade in list(self.open_positions.items()):
            try:
                data = self.fetch_data(symbol)
                if not data.empty:
                    final_price = data['Close'].iloc[-1]
                    trade.exit_date = final_date
                    trade.exit_price = final_price
                    trade.exit_reason = "End of Backtest"
                    cash += final_price * trade.shares
            except:
                pass
        
        self.equity_curve = daily_values
        
        # Ergebnisse berechnen
        results = self._calculate_metrics(cash)
        
        return results
    
    def _calculate_metrics(self, final_cash: float) -> dict:
        """Performance-Metriken berechnen"""
        closed_trades = [t for t in self.trades if t.exit_date is not None]
        
        if not closed_trades:
            return {"error": "Keine abgeschlossenen Trades"}
        
        # Grundlegende Statistiken
        wins = [t for t in closed_trades if t.is_win]
        losses = [t for t in closed_trades if not t.is_win]
        
        total_pnl = sum(t.pnl for t in closed_trades)
        win_rate = len(wins) / len(closed_trades) * 100 if closed_trades else 0
        
        avg_win = np.mean([t.pnl_pct for t in wins]) if wins else 0
        avg_loss = np.mean([t.pnl_pct for t in losses]) if losses else 0
        
        profit_factor = abs(sum(t.pnl for t in wins) / sum(t.pnl for t in losses)) if losses and sum(t.pnl for t in losses) != 0 else float('inf')
        
        # Equity Curve Analyse
        if self.equity_curve:
            equity_values = [v for _, v in self.equity_curve]
            peak = np.maximum.accumulate(equity_values)
            drawdown = (equity_values - peak) / peak
            max_drawdown = np.min(drawdown) * 100
            
            # Returns für Sharpe Ratio
            returns = pd.Series(equity_values).pct_change().dropna()
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() != 0 else 0
        else:
            max_drawdown = 0
            sharpe_ratio = 0
        
        # Buy-and-Hold Vergleich
        buy_hold_return = self._calculate_buy_and_hold()
        
        return {
            "start_date": self.config.start_date,
            "end_date": self.config.end_date,
            "initial_capital": self.config.initial_capital,
            "final_capital": final_cash,
            "total_return": total_pnl,
            "total_return_pct": (total_pnl / self.config.initial_capital) * 100,
            "total_trades": len(closed_trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": win_rate,
            "avg_win_pct": avg_win,
            "avg_loss_pct": avg_loss,
            "profit_factor": profit_factor,
            "max_drawdown_pct": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "buy_hold_return_pct": buy_hold_return,
            "strategy_vs_buyhold": ((final_cash - self.config.initial_capital) / self.config.initial_capital * 100) - buy_hold_return,
            "trades": closed_trades,
            "equity_curve": self.equity_curve
        }
    
    def _calculate_buy_and_hold(self) -> float:
        """Buy-and-Hold Strategie fuer Vergleich"""
        returns = []
        for symbol in self.config.symbols:
            try:
                data = self.fetch_data(symbol)
                if not data.empty:
                    start_price = data['Close'].iloc[0]
                    end_price = data['Close'].iloc[-1]
                    symbol_return = ((end_price - start_price) / start_price) * 100
                    returns.append(symbol_return)
            except:
                pass
        
        return np.mean(returns) if returns else 0


def generate_report(results: dict) -> str:
    """Backtest-Report generieren"""
    
    report = f"""
{'='*70}
                    BACKTEST REPORT
{'='*70}

ZEITRAUM
--------
Von:        {results['start_date']}
Bis:        {results['end_date']}
Dauer:      {(datetime.strptime(results['end_date'], '%Y-%m-%d') - datetime.strptime(results['start_date'], '%Y-%m-%d')).days} Tage

KAPITAL
-------
Start:      EUR {results['initial_capital']:,.2f}
Ende:       EUR {results['final_capital']:,.2f}
Gewinn:     EUR {results['total_return']:+,.2f} ({results['total_return_pct']:+.2f}%)

PERFORMANCE-METRIKEN
--------------------
Gesamt-Trades:      {results['total_trades']}
Gewinn-Trades:      {results['winning_trades']}
Verlust-Trades:     {results['losing_trades']}
Win-Rate:           {results['win_rate']:.1f}%

Avg. Gewinn:        {results['avg_win_pct']:+.2f}%
Avg. Verlust:       {results['avg_loss_pct']:+.2f}%
Profit Factor:      {results['profit_factor']:.2f}

Max. Drawdown:      {results['max_drawdown_pct']:.2f}%
Sharpe Ratio:       {results['sharpe_ratio']:.2f}

VERGLEICH
---------
Strategie:          {results['total_return_pct']:+.2f}%
Buy & Hold:         {results['buy_hold_return_pct']:+.2f}%
Outperformance:     {results['strategy_vs_buyhold']:+.2f}%

{'='*70}
"""
    
    # Trade-Details
    if results['trades']:
        report += "\nTRADE-HISTORIE\n----------------\n"
        for trade in results['trades'][:20]:  # Erste 20 Trades
            report += f"""
#{trade.id}: {trade.symbol}
  Einstieg:   {trade.entry_date.strftime('%Y-%m-%d')} @ ${trade.entry_price:.2f}
  Austieg:    {trade.exit_date.strftime('%Y-%m-%d')} @ ${trade.exit_price:.2f}
  Shares:     {trade.shares}
  P&L:        ${trade.pnl:+.2f} ({trade.pnl_pct:+.2f}%)
  Grund:      {trade.exit_reason}
"""
        
        if len(results['trades']) > 20:
            report += f"\n... und {len(results['trades']) - 20} weitere Trades\n"
    
    report += "\n" + "="*70 + "\n"
    
    return report


def main():
    """Hauptfunktion"""
    
    # Konfiguration
    config = BacktestConfig(
        symbols=["AAPL", "TSLA", "NVDA"],
        start_date="2024-01-01",
        end_date="2025-03-22",  # Bis heute
        initial_capital=10000.0,
        sma_short=20,
        sma_long=50,
        stop_loss_pct=0.05,
        take_profit_pct=0.15,  # Höher für Trend-Following
        max_position_pct=0.33
    )
    
    # Backtest durchführen
    backtester = Backtester(config)
    results = backtester.run()
    
    # Report anzeigen
    report = generate_report(results)
    print(report)
    
    # Report speichern
    reports_dir = Path("/data/.openclaw/workspace/trading_data/backtests")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = reports_dir / f"backtest_{timestamp}.txt"
    
    with open(report_file, "w") as f:
        f.write(report)
    
    print(f"\nReport gespeichert: {report_file}")
    
    return results


if __name__ == "__main__":
    results = main()
