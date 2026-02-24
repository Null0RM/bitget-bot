# Bitget Bot — Session Notes

## What Was Built

A production-ready Bitget USDT-M perpetual futures trading bot using RSI+MACD strategy.

## Key Implementation Decisions

### RSI Lookback Window
The strategy uses a 5-bar RSI lookback (`RSI_LOOKBACK=5`) to decouple RSI extreme timing from the MACD crossover. Without this, trades never trigger because RSI extreme and MACD crossover rarely coincide on the exact same bar.

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
| BTCUSDT  | 3      | 0.0%  | -297.01   | 2.97%    | -1.1876 |
| ETHUSDT  | 6      | 33.3% | -5.96     | 1.99%    | -0.0000 |
| HYPEUSDT | 4      | 25.0% | -102.93   | 1.99%    | -0.2584 |

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
