# Bitget EMA Trend Futures Trading Bot

A production-ready Python trading bot for **USDT-M perpetual futures** on [Bitget](https://www.bitget.com), using an **EMA Crossover + RSI Momentum Filter** strategy with risk-managed position sizing, a bar-by-bar backtesting engine, and **Telegram trade alerts**.

---

## Features

- **EMA Crossover + RSI Filter strategy** — Enters longs when EMA9 crosses above EMA21 with price above EMA50 and RSI confirming upside momentum; enters shorts on the mirror condition
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

# RSI (momentum filter, not reversal signal)
RSI_PERIOD=14
RSI_LONG_MIN=45    # RSI must be above this to enter a long
RSI_LONG_MAX=70    # RSI must be below this to enter a long (not overbought)
RSI_SHORT_MIN=30   # RSI must be above this to enter a short (not oversold)
RSI_SHORT_MAX=55   # RSI must be below this to enter a short

# EMA crossover periods
EMA_FAST=9
EMA_SLOW=21
EMA_TREND=50       # trend direction filter
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
  BTCUSDT           16   31.2%      -114.74      6.82%  -0.1228
  ETHUSDT           11   45.5%      +394.70      3.94%   0.5367
  HYPEUSDT          18   50.0%      +917.39      2.97%   0.9189
----------------------------------------------------------------------
  TOTAL                            +1197.35
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
| **BUY** | EMA9 crosses **above** EMA21 **AND** close > EMA50 **AND** `RSI_LONG_MIN` ≤ RSI ≤ `RSI_LONG_MAX` |
| **SELL** | EMA9 crosses **below** EMA21 **AND** close < EMA50 **AND** `RSI_SHORT_MIN` ≤ RSI ≤ `RSI_SHORT_MAX` |

This is a **trend-following** strategy:

- **EMA crossover (9/21)** detects the momentum shift — the fast EMA crossing the slow EMA signals that short-term momentum has changed direction.
- **EMA trend filter (50)** ensures you only trade in the direction of the prevailing trend. Longs require price above EMA50; shorts require price below it.
- **RSI momentum filter** avoids entering when momentum is already exhausted. For longs, RSI must be in `[45, 70]` — confirming bullish momentum without being overbought. For shorts, RSI must be in `[30, 55]`.

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
