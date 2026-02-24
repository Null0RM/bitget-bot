# Bitget Bot — Session Notes

## What Was Built

A production-ready Bitget USDT-M perpetual futures trading bot using an EMA Crossover + RSI Momentum Filter strategy.

## Strategy: EMA Trend Following

Replaced the original RSI+MACD counter-trend reversal strategy with a trend-following approach:

- **Long**: EMA9 crosses above EMA21 + price > EMA50 (uptrend) + RSI in [45, 70]
- **Short**: EMA9 crosses below EMA21 + price < EMA50 (downtrend) + RSI in [30, 55]

**Why the change**: The RSI+MACD strategy tried to catch reversals (buy oversold, sell overbought). In trending crypto markets this produced 0–25% win rates with very few signals. The EMA trend strategy trades *with* momentum, generates more signals (4–5× more trades), and achieved 45–50% win rates with positive PnL on ETH and HYPE.

**Backtest comparison (4H, ~90 days, $10k starting balance)**:

| Symbol | Old Trades | Old Win% | Old PnL | New Trades | New Win% | New PnL |
|--------|-----------|---------|---------|-----------|---------|---------|
| BTC | 3 | 0% | -297 | 16 | 31% | -115 |
| ETH | 6 | 33% | -6 | 11 | 45% | +395 |
| HYPE | 4 | 25% | -103 | 18 | 50% | +917 |
| **Total** | | | **-406** | | | **+1197** |

## Key Implementation Decisions

### Position Sizing (No Leverage Multiplier)
```
quantity = (balance × risk_pct%) / (entry × sl_pct%)
```
Leverage is NOT applied in position size or PnL calculation — leverage affects margin requirements at the exchange, not the notional P&L math.

### API History Depth
Bitget stores ~90 days of candle history regardless of timeframe. 4H candles (~540 bars) give the most useful backtest coverage. Pagination walks backwards using `endTime`.

### Multi-Symbol Threading
Live mode spawns one daemon thread per symbol. A shared `threading.Lock` serializes the balance-fetch → order-place sequence to prevent two symbols from sizing against the same balance simultaneously.

## File Overview

| File | Purpose |
|------|---------|
| `bot.py` | CLI entry point (`--live`, `--backtest`, `--symbols`, `--tf`, `--limit`, `--out-dir`) |
| `config.py` | Loads `.env` into a typed `Config` dataclass |
| `bitget_client.py` | Bitget V2 REST API wrapper with HMAC-SHA256 auth |
| `indicators.py` | RSI (Wilder's EWM), MACD, signal generation with lookback |
| `strategy.py` | `RSIMACDStrategy` class wrapping indicators |
| `risk_manager.py` | Position sizing and SL/TP calculation |
| `backtest.py` | Bar-by-bar backtesting engine + dark-themed chart output |
| `telegram_notifier.py` | Telegram alerts (silently disabled if token not set) |

## Backtest Results (4H, ~540 bars, $10k starting balance)

| Symbol   | Trades | Win%  | PnL       | Drawdown | Sharpe  |
|----------|--------|-------|-----------|----------|---------|
| BTCUSDT  | 16     | 31.2% | -114.74   | 6.82%    | -0.1228 |
| ETHUSDT  | 11     | 45.5% | +394.70   | 3.94%    | +0.5367 |
| HYPEUSDT | 18     | 50.0% | +917.39   | 2.97%    | +0.9189 |

## Repository

`git@github.com:Null0RM/bitget-bot.git`

## Common Commands

```bash
# Backtest multiple symbols
python3 bot.py --backtest --symbols BTCUSDT,ETHUSDT,HYPEUSDT --tf 4H --limit 1000

# Live trading
python3 bot.py --live --symbols BTCUSDT,ETHUSDT --tf 15m

# Save charts to custom directory
python3 bot.py --backtest --symbols BTCUSDT,ETHUSDT --tf 4H --out-dir results/
```
