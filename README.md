# Bitget RSI+MACD Futures Trading Bot

A production-ready Python trading bot for **USDT-M perpetual futures** on [Bitget](https://www.bitget.com), using a combined **RSI + MACD** strategy with risk-managed position sizing, a bar-by-bar backtesting engine, and **Telegram trade alerts**.

---

## Features

- **RSI + MACD strategy** — Enters longs when RSI was recently oversold and MACD crosses up; enters shorts when RSI was recently overbought and MACD crosses down
- **Risk-based position sizing** — Risks a fixed % of balance per trade; stop-loss and take-profit calculated automatically
- **Backtesting engine** — Simulates bar-by-bar with SL/TP logic, outputs win rate, PnL, max drawdown, Sharpe ratio, and an equity curve chart
- **Multi-symbol support** — Backtest or trade multiple coins in one command; live mode runs each symbol in its own thread
- **Telegram alerts** — Notifies on trade open, close, and errors
- **Bitget V2 API** — HMAC-SHA256 authenticated REST client with automatic candle pagination

---

## Project Structure

```
bitget-bot/
├── bot.py               # Main entry point (CLI)
├── config.py            # Config loader from .env
├── bitget_client.py     # Bitget V2 REST API wrapper
├── indicators.py        # RSI, MACD, signal generation
├── strategy.py          # RSI+MACD strategy class
├── risk_manager.py      # Position sizing, SL/TP calculation
├── backtest.py          # Backtesting engine + metrics + chart
├── telegram_notifier.py # Telegram alert sender
├── requirements.txt     # Python dependencies
└── backtest/            # Output directory for backtest charts (gitignored)
```

---

## Installation

```bash
git clone git@github.com:Null0RM/bitget-bot.git
cd bitget-bot
pip install -r requirements.txt
cp .env.example .env   # then fill in your credentials
```

---

## Configuration

All settings are loaded from `.env`. Copy `.env.example` and fill in your values:

```env
# Bitget API credentials
BITGET_API_KEY=
BITGET_SECRET=
BITGET_PASSPHRASE=

# Telegram (optional — leave blank to disable alerts)
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=

# Trading
SYMBOL=BTCUSDT
PRODUCT_TYPE=USDT-FUTURES
MARGIN_COIN=USDT
TIMEFRAME=15m
LEVERAGE=5

# Risk management
RISK_PCT=1.0       # % of balance to risk per trade
SL_PCT=2.0         # stop-loss distance from entry (%)
TP_PCT=4.0         # take-profit distance from entry (%)

# RSI
RSI_PERIOD=14
RSI_OVERSOLD=30
RSI_OVERBOUGHT=70
RSI_LOOKBACK=5     # bars to look back for RSI extreme before MACD crossover

# MACD
MACD_FAST=12
MACD_SLOW=26
MACD_SIGNAL=9
```

---

## Usage

### Backtest

Run a backtest on a single symbol:

```bash
python bot.py --backtest --symbol BTCUSDT --tf 4H --limit 1000
```

Run a backtest on multiple symbols at once:

```bash
python bot.py --backtest --symbols BTCUSDT,ETHUSDT,HYPEUSDT --tf 4H --limit 1000
```

Charts are saved to `backtest/` by default. Override with `--out-dir`:

```bash
python bot.py --backtest --symbols BTCUSDT,ETHUSDT --tf 4H --out-dir results/
```

**Example output:**

```
======================================================================
  SYMBOL        TRADES    WIN%          PNL   DRAWDOWN   SHARPE
----------------------------------------------------------------------
  BTCUSDT            3    0.0%      -297.01      2.97%  -1.1876
  ETHUSDT            6   33.3%        -5.96      1.99%  -0.0000
  HYPEUSDT           4   25.0%      -102.93      1.99%  -0.2584
----------------------------------------------------------------------
  TOTAL                             -405.90
======================================================================
```

### Live Trading

Trade a single symbol:

```bash
python bot.py --live --symbol BTCUSDT --tf 15m
```

Trade multiple symbols concurrently (one thread per symbol):

```bash
python bot.py --live --symbols BTCUSDT,ETHUSDT,SOLUSDT --tf 15m
```

> **Note:** Live mode requires `BITGET_API_KEY`, `BITGET_SECRET`, and `BITGET_PASSPHRASE` set in `.env`.

---

## Strategy Logic

### Signal Generation

| Signal | Condition |
|--------|-----------|
| **BUY** | RSI was below `RSI_OVERSOLD` within the last `RSI_LOOKBACK` bars **AND** MACD line crosses above signal line |
| **SELL** | RSI was above `RSI_OVERBOUGHT` within the last `RSI_LOOKBACK` bars **AND** MACD line crosses below signal line |

The `RSI_LOOKBACK` window (default 5 bars) allows the MACD crossover confirmation to occur slightly after the RSI extreme — which is how this setup is used in practice. RSI flags the exhaustion zone; MACD confirms the momentum turn.

### Risk Management

- **Position size** = `(balance × risk_pct%) / (entry × sl_pct%)`
- **Stop-loss** = `entry ± entry × sl_pct%` (minus for long, plus for short)
- **Take-profit** = `entry ± entry × tp_pct%` (plus for long, minus for short)

With default settings (`RISK_PCT=1`, `SL_PCT=2`, `TP_PCT=4`) each trade risks 1% of balance with a 1:2 risk/reward ratio.

---

## CLI Reference

| Flag | Description | Default |
|------|-------------|---------|
| `--live` | Run live trading loop | — |
| `--backtest` | Run backtesting engine | — |
| `--symbol` | Single trading symbol | `.env` value |
| `--symbols` | Comma-separated symbol list | — |
| `--tf` | Candle timeframe (`1m` `15m` `1H` `4H` `1D` …) | `.env` value |
| `--limit` | Number of historical candles to fetch | `1000` |
| `--out-dir` | Directory to save backtest charts | `backtest/` |

---

## Supported Timeframes

`1m` · `3m` · `5m` · `15m` · `30m` · `1H` · `4H` · `6H` · `12H` · `1D` · `1W`

---

## Disclaimer

This bot is provided for educational purposes. Cryptocurrency futures trading involves significant risk. Always backtest thoroughly and never risk more than you can afford to lose.
