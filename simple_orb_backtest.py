#!/usr/bin/env python3
"""
Simple ORB backtest focusing on the requested assets: SPY, QQQ, ES, NQ
Uses daily data with ORB approximation from previous day's range
"""

import yfinance as yf
import pandas as pd
import numpy as np

# ============================= Configuration =============================
CONFIG = {
    "symbols": ["SPY", "QQQ", "ES=F", "NQ=F"],
    "start_date": "2024-01-01",
    "end_date": "2026-03-31",
    "initial_capital": 10000.0,
    "risk_per_trade": 0.01,           # 1% risk per trade
    "max_daily_trades": 1,            # ORB typically 1 trade per day
    "opening_range_multiplier": 1.0,  # Break at ORB high/low
    "volume_multiplier": 1.5,         # Volume confirmation
    "profit_target_r": 2.0,           # 2R profit target
    "stop_loss_r": 1.0,               # 1R stop loss
    "trail_after_r": 1.0,             # Trail after 1R profit
    "trail_distance_r": 0.5,          # Trail distance
}

# ============================= Helper Functions =============================
def get_orb_from_previous_day(df):
    """
    Approximate ORB using previous day's high/low
    For daily chart, ORB of today is approximated by yesterday's range
    """
    if len(df) < 2:
        return 0, 0, 0, 0
    
    # Use previous day as ORB for today
    prev_day = df.iloc[-2]
    orb_high = prev_day["High"]
    orb_low = prev_day["Low"]
    orb_range = orb_high - orb_low
    
    # Volume ratio (today's volume vs average)
    if len(df) >= 20:
        vol_ma = df["Volume"].rolling(20).mean().iloc[-1]
        vol_ratio = df["Volume"].iloc[-1] / vol_ma if vol_ma > 0 else 0
    else:
        vol_ratio = 1.0
    
    return orb_high, orb_low, orb_range, vol_ratio

def atr(df, period=14):
    """Calculate Average True Range"""
    high_low = df["High"] - df["Low"]
    high_close = np.abs(df["High"] - df["Close"].shift())
    low_close = np.abs(df["Low"] - df["Close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

# ============================= Backtest =============================
def backtest_symbol(symbol, config):
    """Run ORB backtest for a single symbol"""
    print(f"\nBacktesting {symbol}...")
    
    # Fetch data
    df = yf.Ticker(symbol).history(
        start=config["start_date"], 
        end=config["end_date"]
    )
    
    if df.empty or len(df) < 20:
        print(f"  Insufficient data")
        return None
    
    # Initialize
    cash = config["initial_capital"]
    position = None
    trades = []
    equity_curve = [{"date": df.index[0], "equity": cash}]
    
    # Process each day (skip first day as we need previous day for ORB)
    for i in range(1, len(df)):
        today = df.iloc[i]
        prev_day = df.iloc[i-1]
        date = df.index[i]
        
        # Calculate ORB from previous day
        orb_high = prev_day["High"]
        orb_low = prev_day["Low"]
        orb_range = orb_high - orb_low
        
        if orb_range <= 0:
            # Skip if invalid ORB
            equity_curve.append({"date": date, "equity": cash})
            continue
        
        # Volume confirmation
        vol_ma = df["Volume"].iloc[max(0, i-19):i+1].mean()
        vol_ratio = today["Volume"] / vol_ma if vol_ma > 0 else 0
        
        # Check for long signal (break above ORB high)
        if position is None and today["High"] > orb_high and vol_ratio >= config["volume_multiplier"]:
            # Calculate stop loss
            atr_val = atr(df.iloc[:i+1]).iloc[-1]
            stop_loss = max(
                orb_low,                                      # ORB low stop
                today["Close"] - (config["stop_loss_r"] * atr_val)  # ATR stop
            )
            
            # Ensure stop is below entry
            if stop_loss >= today["Close"]:
                stop_loss = today["Close"] - (1.0 * atr_val)
            
            # Calculate position size
            risk_per_share = today["Close"] - stop_loss
            if risk_per_share <= 0:
                continue
            
            # Current equity (cash + position value)
            position_value = position["shares"] * today["Close"] if position else 0
            equity = cash + position_value
            
            risk_amount = equity * config["risk_per_trade"]
            shares = int(risk_amount / risk_per_share)
            
            # Limit by cash (use 50% max per trade)
            max_shares_by_cash = int((cash * 0.5) / today["Close"])
            shares = min(shares, max_shares_by_cash)
            
            if shares <= 0:
                continue
            
            # Enter position
            cost = shares * today["Close"]
            if cost > cash:
                continue
            
            cash -= cost
            position = {
                "shares": shares,
                "entry": today["Close"],
                "stop_loss": stop_loss,
                "entry_date": date,
                "highest": today["Close"],
                "trail_stop": None,
                "partial_taken": False
            }
            
            trades.append({
                "date": date,
                "action": "BUY",
                "symbol": symbol,
                "shares": shares,
                "price": today["Close"],
                "cost": cost,
                "reason": f"ORB breakout (Vol: {vol_ratio:.1f}x)",
                "orb_high": orb_high,
                "orb_low": orb_low,
                "stop_loss": stop_loss
            })
        
        # Manage existing position
        if position is not None:
            # Update highest high
            if today["High"] > position["highest"]:
                position["highest"] = today["High"]
                
                # Update trailing stop if activated
                profit_per_share = position["highest"] - position["entry"]
                initial_risk = position["entry"] - position["stop_loss"]
                
                if initial_risk > 0:
                    r_multiple = profit_per_share / initial_risk
                    
                    if r_multiple >= config["trail_after_r"]:
                        trail_amount = config["trail_distance_r"] * initial_risk
                        new_trail = position["highest"] - trail_amount
                        
                        if position["trail_stop"] is None or new_trail > position["trail_stop"]:
                            position["trail_stop"] = new_trail
            
            # Check exit conditions
            exit_triggered = False
            exit_price = today["Close"]
            exit_reason = None
            
            # Profit target (2R)
            profit_per_share = position["highest"] - position["entry"]
            initial_risk = position["entry"] - position["stop_loss"]
            
            if initial_risk > 0:
                r_multiple = profit_per_share / initial_risk
                
                if r_multiple >= config["profit_target_r"]:
                    exit_triggered = True
                    exit_reason = "PROFIT_TARGET"
            
            # Stop loss
            elif today["Low"] <= position["stop_loss"]:
                exit_triggered = True
                exit_reason = "STOP_LOSS"
                exit_price = position["stop_loss"]  # Assume filled at stop
            
            # Trailing stop
            elif position["trail_stop"] is not None and today["Low"] <= position["trail_stop"]:
                exit_triggered = True
                exit_reason = "TRAILING_STOP"
                exit_price = position["trail_stop"]
            
            if exit_triggered:
                proceeds = position["shares"] * exit_price
                cash += proceeds
                pnl = proceeds - (position["shares"] * position["entry"])
                
                trades.append({
                    "date": date,
                    "action": "SELL",
                    "symbol": symbol,
                    "shares": position["shares"],
                    "price": exit_price,
                    "proceeds": proceeds,
                    "pnl": pnl,
                    "reason": exit_reason,
                    "hold_days": (date - position["entry_date"]).days
                })
                
                position = None
        
        # Update equity curve
        position_value = 0
        if position is not None:
            position_value = position["shares"] * today["Close"]
        
        equity_curve.append({
            "date": date,
            "equity": cash + position_value
        })
    
    # Close any open position at end
    if position is not None:
        final_price = df["Close"].iloc[-1]
        proceeds = position["shares"] * final_price
        cash += proceeds
        pnl = proceeds - (position["shares"] * position["entry"])
        
        trades.append({
            "date": df.index[-1],
            "action": "SELL",
            "symbol": symbol,
            "shares": position["shares"],
            "price": final_price,
            "proceeds": proceeds,
            "pnl": pnl,
            "reason": "END_OF_BACKTEST",
            "hold_days": (df.index[-1] - position["entry_date"]).days
        })
    
    # Calculate statistics
    if not trades:
        return {
            "symbol": symbol,
            "total_trades": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "final_equity": config["initial_capital"],
            "return_pct": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "profit_factor": 0,
            "max_drawdown": 0,
            "trades": [],
            "equity_curve": equity_curve
        }
    
    # Filter completed trades (sell trades with P&L)
    sell_trades = [t for t in trades if t["action"] == "SELL" and "pnl" in t]
    
    if not sell_trades:
        win_rate = 0
        total_pnl = 0
        avg_win = 0
        avg_loss = 0
        profit_factor = 0
    else:
        wins = [t for t in sell_trades if t["pnl"] > 0]
        losses = [t for t in sell_trades if t["pnl"] <= 0]
        
        win_rate = len(wins) / len(sell_trades) * 100 if sell_trades else 0
        total_pnl = sum(t["pnl"] for t in sell_trades)
        avg_win = np.mean([t["pnl"] for t in wins]) if wins else 0
        avg_loss = np.mean([t["pnl"] for t in losses]) if losses else 0
        profit_factor = abs(avg_win * len(wins) / (avg_loss * len(losses))) if losses and avg_loss != 0 else float('inf') if wins else 0
    
    # Calculate max drawdown
    if len(equity_curve) > 1:
        equity_series = [point["equity"] for point in equity_curve]
        running_max = np.maximum.accumulate(equity_series)
        drawdown = (np.array(equity_series) - running_max) / running_max * 100
        max_drawdown = abs(np.min(drawdown)) if len(drawdown) > 0 else 0
    else:
        max_drawdown = 0
    
    final_equity = equity_curve[-1]["equity"] if equity_curve else config["initial_capital"]
    return_pct = (final_equity / config["initial_capital"] - 1) * 100
    
    return {
        "symbol": symbol,
        "total_trades": len(sell_trades),
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "final_equity": final_equity,
        "return_pct": return_pct,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "max_drawdown": max_drawdown,
        "trades": sell_trades,
        "equity_curve": equity_curve
    }

# ============================= Main =============================
def main():
    print("="*70)
    print("SIMPLE ORB BACKTEST - US MARKET FOCUS")
    print("="*70)
    print(f"Period: {CONFIG['start_date']} to {CONFIG['end_date']}")
    print(f"Initial Capital: ${CONFIG['initial_capital']:,.2f}")
    print(f"Risk per Trade: {CONFIG['risk_per_trade']*100:.1f}%")
    print(f"Profit Target: {CONFIG['profit_target_r']}R")
    print(f"Stop Loss: {CONFIG['stop_loss_r']}R")
    print(f"Volume Confirmation: {CONFIG['volume_multiplier']}x average")
    print("-"*70)
    
    results = {}
    for symbol in CONFIG["symbols"]:
        results[symbol] = backtest_symbol(symbol, CONFIG)
    
    # Print summary
    print("\n" + "="*70)
    print("BACKTEST RESULTS SUMMARY")
    print("="*70)
    print(f"{'Symbol':<8} {'Trades':<8} {'Win%':<8} {'Return':<10} {'PF':<8} {'DD%':<8} {'Avg Win':<10} {'Avg Loss':<10}")
    print("-"*70)
    
    for symbol, result in results.items():
        if result is None:
            print(f"{symbol:<8} {'NO DATA':<8} {'-':<6} {'-':<10} {'-':<6} {'-':<6} {'-':<10} {'-':<10}")
            continue
        
        print(f"{symbol:<8} {result['total_trades']:<8} {result['win_rate']:<7.1f}% "
              f"${result['total_pnl']:<9.2f} {result['return_pct']:<9.2f}% "
              f"{result['profit_factor']:<7.2f} {result['max_drawdown']:<7.2f}% "
              f"${result['avg_win']:<9.2f} ${result['avg_loss']:<9.2f}")
    
    print("-"*70)
    
    # Detailed analysis
    print("\nDETAILED ANALYSIS:")
    print("-"*70)
    for symbol, result in results.items():
        if result is None or result['total_trades'] == 0:
            print(f"\n{symbol}: No trades executed")
            continue
        
        print(f"\n{symbol}:")
        print(f"  Period: {CONFIG['start_date']} to {CONFIG['end_date']}")
        print(f"  Total Trades: {result['total_trades']}")
        print(f"  Win Rate: {result['win_rate']:.1f}%")
        print(f"  Total P&L: ${result['total_pnl']:.2f}")
        print(f"  Final Equity: ${result['final_equity']:,.2f}")
        print(f"  Return: {result['return_pct']:.2f}%")
        print(f"  Average Win: ${result['avg_win']:.2f}")
        print(f"  Average Loss: ${result['avg_loss']:.2f}")
        print(f"  Profit Factor: {result['profit_factor']:.2f}")
        print(f"  Max Drawdown: {result['max_drawdown']:.2f}%")
        
        if result['trades']:
            print(f"  Trade Examples (last 3):")
            for trade in result['trades'][-3:]:
                print(f"    {trade['date'].strftime('%Y-%m-%d')} {trade['action']} "
                      f"{trade['shares']} @ ${trade['price']:.2f} "
                      f"P&L: ${trade['pnl']:.2f} ({trade['reason']})")
    
    # Save results
    import json
    from datetime import datetime
    
    # Prepare results for JSON serialization
    json_results = {}
    for symbol, result in results.items():
        if result is None:
            json_results[symbol] = None
            continue
        
        result_copy = result.copy()
        # Convert datetime objects in equity_curve
        if 'equity_curve' in result_copy:
            for point in result_copy['equity_curve']:
                if hasattr(point['date'], 'isoformat'):
                    point['date'] = point['date'].isoformat()
        # Convert datetime objects in trades
        if 'trades' in result_copy:
            for trade in result_copy['trades']:
                if hasattr(trade['date'], 'isoformat'):
                    trade['date'] = trade['date'].isoformat()
        json_results[symbol] = result_copy
    
    results_file = "/data/.openclaw/workspace/orb_backtest_results.json"
    with open(results_file, "w") as f:
        json.dump(json_results, f, indent=2, default=str)
    
    print(f"\nResults saved to: {results_file}")
    
    # Provide recommendations
    print("\n" + "="*70)
    print("RECOMMENDATIONS FOR ORB ENHANCEMENT")
    print("="*70)
    
    # Find best performing symbol
    valid_results = {k: v for k, v in results.items() if v is not None and v['total_trades'] > 0}
    if valid_results:
        best_by_return = max(valid_results.items(), key=lambda x: x[1]['return_pct'])
        best_by_winrate = max(valid_results.items(), key=lambda x: x[1]['win_rate'])
        best_by_pf = max(valid_results.items(), key=lambda x: x[1]['profit_factor'] if x[1]['profit_factor'] != float('inf') else 0)
        
        print(f"🏆 Best Return: {best_by_return[0]} ({best_by_return[1]['return_pct']:.2f}%)")
        print(f"🎯 Best Win Rate: {best_by_winrate[0]} ({best_by_winrate[1]['win_rate']:.1f}%)")
        print(f"⚡ Best Profit Factor: {best_by_pf[0]} ({best_by_pf[1]['profit_factor']:.2f})")
        
        print("\n📊 Asset-Specific Insights:")
        for symbol, result in valid_results.items():
            if result['total_trades'] >= 5:  # Minimum trades for meaningful stats
                print(f"  {symbol}: {result['win_rate']:.1f}% win rate, "
                      f"{result['return_pct']:.2f}% return, "
                      f"PF {result['profit_factor']:.2f}")
            elif result['total_trades'] > 0:
                print(f"  {symbol}: {result['total_trades']} trades (insufficient for stats)")
            else:
                print(f"  {symbol}: No trades triggered")
    
    print("\n🔧 Suggested Parameter Adjustments:")
    print("  • For ES/SPY (stable): Consider lower volume multiplier (1.2-1.3)")
    print("  • For NQ/QQQ (volatile): Consider higher volume multiplier (1.8-2.0)")
    print("  • Test different ORB breakout multipliers (0.5-2.0)")
    print("  • Consider time-based exits (end of day if not exited)")
    print("  • Add weekday filters (avoid Mondays/Fridays if needed)")
    print("="*70)

if __name__ == "__main__":
    main()