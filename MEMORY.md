# MEMORY.md - Long-Term Memory

## Email Sending (Gmail via App Password)
- Method: Python smtplib or Himalaya CLI
- App Password stored in `~/.secrets/mail/gmail.pass` (chmod 600)
- Python example: use smtplib with STARTTLS on port 587
- Himalaya config: `~/.config/himalaya/config.toml` with `auth.cmd = "cat ~/.secrets/mail/gmail.pass"`
- Verified: Test emails sent successfully (see memory/2026-03-27.md)
- ADX bug identified and fixed: plus_dm/minus_dm now preserve index, enabling correct ADX values and functional trend filter.
## Silent Replies
When you have nothing to say, respond with ONLY: NO_REPLY
⚠️ Rules:
- It must be your ENTIRE message — nothing else
- Never append it to an actual response (never include "NO_REPLY" in real replies)
- Never wrap it in markdown or code blocks
❌ Wrong: "Here's help... NO_REPLY"
❌ Wrong: "NO_REPLY"
✅ Right: NO_REPLY
## Heartbeats
Heartbeat prompt: Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK.
If you receive a heartbeat poll (a user message matching the heartbeat prompt above), and there is nothing that needs attention, reply exactly:
HEARTBEAT_OK
OpenClaw treats a leading/trailing "HEARTBEAT_OK" as a heartbeat ack (and may discard it).
If something needs attention, do NOT include "HEARTBEAT_OK"; reply with the alert text instead.
## Runtime
Runtime: agent=main | host=ce31d7c65e07 | repo=/data/.openclaw/workspace | os=Linux 6.8.0-101-generic (x64) | node=v22.22.1 | model=nvidia/nvidia/nemotron-3-super-120b-a12b | default_model=nvidia/nemotron-3-super-120b-a12b | channel=telegram | capabilities=inlineButtons | thinking=low
Reasoning: off (hidden unless on/stream). Toggle /reasoning; /status shows Reasoning when enabled.

## Trading Bot Notes (2026-03-30)
- Bot runs hourly via heartbeat (trader_daemon.py) using trader_v5.py.
- Parameters optimized: risk/trade=0.02, SL-ATR=2.5, trail-ATR=3.0, partial-profit=0.25.
- ML overlay deactivated; watchlist_adhoc.txt monitors XLE, LMT, GLD, XOM, QQQ, DAL for potential BUY signals.
- Last run at 13:00 showed flat SPY/QQQ pair, equity ~9,951 EUR (-0.49% YTD).
- No open positions due to ADX < 20 and no SMA cross.

## ORB_Bot Notes (2026-03-31)
- New independent day trading bot using ORB (Opening Range Breakout) strategy
- Focuses on liquid ETFs and large-cap stocks: SPY, QQQ, IWM, DIA, AAPL, MSFT, GOOGL, AMZN, TSLA, NVDA, META, AMD, NFLX
- Uses previous day's high/low as ORB proxy for daily timeframe analysis
- Risk management: 1% risk per trade, max 5 trades per day, 5% max portfolio risk
- Profit target: 2R, Stop loss: 1R, Trailing stop activated after 1R profit
- Memory tracking: Separate memory file at `/data/.openclaw/workspace/orb_trading_data/memory.md`
- Daily reports stored in `/data/.openclaw/workspace/orb_trading_data/reports/`
- First run completed on 2026-04-01 - no signals generated (waiting for ORB breakout conditions)