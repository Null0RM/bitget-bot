#!/usr/bin/env python3
"""
Bitget Perpetual Futures Trading Bot — RSI + MACD Strategy

Single symbol:
    python bot.py --backtest --symbol BTCUSDT --tf 4H --limit 1000
    python bot.py --live    --symbol BTCUSDT --tf 15m

Multiple symbols:
    python bot.py --backtest --symbols BTCUSDT,ETHUSDT,SOLUSDT --tf 4H --limit 1000
    python bot.py --live    --symbols BTCUSDT,ETHUSDT,SOLUSDT --tf 15m
"""

import argparse
import os
import sys
import time
import threading
from datetime import datetime

import pandas as pd

from config import load_config
from bitget_client import BitgetClient, BitgetAPIError
from strategy import HolisticStrategy
from risk_manager import RiskManager
from telegram_notifier import TelegramNotifier
from backtest import BacktestEngine, plot_results

# Bitget granularity → seconds per candle
TF_SECONDS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1H": 3600, "4H": 14400, "6H": 21600, "12H": 43200,
    "1D": 86400, "1W": 604800,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def candles_to_df(candles: list) -> pd.DataFrame:
    df = pd.DataFrame(candles)
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df.set_index("ts")


def resolve_symbols(args, config) -> list:
    """Return the deduplicated list of symbols from CLI args or config."""
    raw = getattr(args, "symbols", None) or getattr(args, "symbol", None) or config.symbol
    seen = set()
    result = []
    for s in raw.split(","):
        sym = s.strip().upper()
        if sym and sym not in seen:
            seen.add(sym)
            result.append(sym)
    return result


def parse_leverages(leverages_str: str, symbols: list, default: int) -> dict:
    """Parse 'BTCUSDT=8,ETHUSDT=6' into per-symbol leverage map."""
    result = {s: default for s in symbols}
    if leverages_str:
        for part in leverages_str.split(","):
            part = part.strip()
            if "=" in part:
                sym, lev = part.split("=", 1)
                result[sym.strip().upper()] = int(lev.strip())
    return result


def print_metrics(metrics: dict, symbol: str, tf: str, leverage: int, balance: float) -> None:
    print("\n" + "=" * 52)
    print(f"  BACKTEST RESULTS — {symbol} {tf}  (x{leverage} lev, ${balance:.0f} start)")
    print("=" * 52)
    print(f"  Trades:        {metrics['num_trades']}")
    print(f"  Win Rate:      {metrics['win_rate']:.2f}%")
    print(f"  Total PnL:     {metrics['total_pnl']:+.4f} USDT")
    print(f"  Max Drawdown:  {metrics['max_drawdown']:.2f}%")
    print(f"  Sharpe Ratio:  {metrics['sharpe_ratio']:.4f}")
    print(f"  Final Balance: {metrics['final_balance']:.4f} USDT")
    print("=" * 52)


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

def run_backtest(args, config) -> None:
    symbols = resolve_symbols(args, config)
    tf = args.tf or config.timeframe
    limit = args.limit
    out_dir = args.out_dir
    balance = args.balance
    leverage_map = parse_leverages(args.leverages, symbols, config.leverage)

    os.makedirs(out_dir, exist_ok=True)

    client = BitgetClient(config.api_key, config.secret, config.passphrase)
    strategy = HolisticStrategy(config)

    summary     = []   # per-symbol metrics for the aggregate table
    all_results = []   # collected for the combined chart

    for symbol in symbols:
        lev = leverage_map[symbol]
        risk_manager = RiskManager(config.collateral_pct, config.sl_pct, config.tp_pct, lev)

        print(f"\n[Backtest] Fetching {limit} candles for {symbol} {tf} (x{lev} leverage) ...")
        candles = client.get_candles(symbol, tf, limit)
        df = candles_to_df(candles)
        print(f"[Backtest] Got {len(df)} candles  ({df.index[0]} → {df.index[-1]})")

        engine = BacktestEngine()
        metrics = engine.run(df, strategy, risk_manager, config, initial_balance=balance)
        print_metrics(metrics, symbol, tf, lev, balance)

        all_results.append({
            "symbol":   symbol,
            "df":       df,
            "trades":   engine.trades,
            "equity":   engine.equity_curve,
            "leverage": lev,
        })
        summary.append({"symbol": symbol, "leverage": lev, **metrics})

    # Single combined chart named backtest_{SYMBOLS}_{TF}.png
    symbols_tag = "_".join(symbols)
    chart_file  = os.path.join(out_dir, f"backtest_{symbols_tag}_{tf}.png")
    plot_results(all_results, tf, output_path=chart_file, config=config)

    # Aggregate summary table when multiple symbols were run
    if len(summary) > 1:
        print("\n" + "=" * 76)
        print(f"  {'SYMBOL':<12} {'LEV':>4} {'TRADES':>7} {'WIN%':>7} {'PNL':>12} {'DRAWDOWN':>10} {'SHARPE':>8}")
        print("-" * 76)
        for m in summary:
            print(
                f"  {m['symbol']:<12} x{m['leverage']:<3} {m['num_trades']:>7} "
                f"{m['win_rate']:>6.1f}% {m['total_pnl']:>+12.2f} "
                f"{m['max_drawdown']:>9.2f}% {m['sharpe_ratio']:>8.4f}"
            )
        total_pnl = sum(m["total_pnl"] for m in summary)
        print("-" * 76)
        print(f"  {'TOTAL':<12} {'':>4} {'':>7} {'':>7} {total_pnl:>+12.2f}")
        print("=" * 76 + "\n")


# ---------------------------------------------------------------------------
# Live — single-symbol loop (runs in its own thread)
# ---------------------------------------------------------------------------

def _live_symbol_loop(
    symbol: str,
    tf: str,
    limit: int,
    config,
    client: BitgetClient,
    strategy: HolisticStrategy,
    risk_manager: RiskManager,
    notifier: TelegramNotifier,
    order_lock: threading.Lock,
) -> None:
    """Trading loop for one symbol. Designed to run inside a daemon thread."""
    tag = f"[{symbol}]"

    # Set leverage once at startup
    try:
        client.set_leverage(symbol, config.leverage, config.margin_coin, config.product_type)
        print(f"{tag} Leverage set to {config.leverage}x")
    except BitgetAPIError as exc:
        print(f"{tag} Warning: could not set leverage — {exc}")

    candle_seconds = TF_SECONDS.get(tf, 900)

    while True:
        try:
            now = datetime.utcnow()
            print(f"\n{tag} [{now.strftime('%Y-%m-%d %H:%M:%S')} UTC] Checking signal ...")

            candles = client.get_candles(symbol, tf, limit)
            df = candles_to_df(candles)
            signal = strategy.get_signal(df)

            # Check for existing open position on this symbol
            positions = client.get_positions(symbol, config.product_type)
            has_open = any(float(p.get("total", 0)) != 0 for p in positions)

            if signal and not has_open:
                side = signal["side"]
                entry = signal["entry_price"]

                # Lock so concurrent symbols don't both read the same balance
                # and each submit orders without the other's margin already reserved
                with order_lock:
                    account = client.get_account(config.margin_coin, config.product_type)
                    balance = float(account.get("available", 0))

                    size = risk_manager.calculate_position_size(balance, entry)
                    sl_price, tp_price = risk_manager.calculate_sl_tp(entry, side)

                    print(
                        f"{tag} Signal: {side.upper()} | Entry: {entry} | "
                        f"SL: {sl_price} | TP: {tp_price} | Size: {size}"
                    )

                    order = client.place_order(
                        symbol=symbol,
                        side=side,
                        size=str(size),
                        order_type="market",
                        tp_price=str(tp_price),
                        sl_price=str(sl_price),
                        product_type=config.product_type,
                        margin_coin=config.margin_coin,
                    )
                    print(f"{tag} Order placed: {order}")

                notifier.trade_opened(
                    symbol=symbol, side=side, entry=entry, size=size,
                    sl=sl_price, tp=tp_price,
                    pattern=signal["pattern"],
                )
            else:
                reason = "position open" if has_open else "no signal"
                print(f"{tag} No action ({reason})")

        except BitgetAPIError as exc:
            print(f"{tag} API error: {exc}")
            notifier.error_alert(f"{symbol} API", str(exc))
        except Exception as exc:
            print(f"{tag} Unexpected error: {exc}")
            notifier.error_alert(f"{symbol}", str(exc))

        # Sleep until the next candle boundary (+ 5 s buffer)
        sleep_secs = candle_seconds - (int(time.time()) % candle_seconds) + 5
        print(f"{tag} Sleeping {sleep_secs}s until next candle ...")
        time.sleep(sleep_secs)


# ---------------------------------------------------------------------------
# Live — orchestrator
# ---------------------------------------------------------------------------

def run_live(args, config) -> None:
    symbols = resolve_symbols(args, config)
    tf = args.tf or config.timeframe
    limit = args.limit

    print(f"[Live] Starting bot | symbols: {', '.join(symbols)} | tf: {tf}")

    client = BitgetClient(config.api_key, config.secret, config.passphrase)
    strategy = HolisticStrategy(config)
    risk_manager = RiskManager(config.collateral_pct, config.sl_pct, config.tp_pct, config.leverage)
    notifier = TelegramNotifier(config.telegram_token, config.telegram_chat_id)
    order_lock = threading.Lock()

    notifier.info(
        f"Bot started: {', '.join(symbols)} | {tf} | Leverage {config.leverage}x"
    )

    threads = []
    for symbol in symbols:
        t = threading.Thread(
            target=_live_symbol_loop,
            args=(symbol, tf, limit, config, client, strategy, risk_manager, notifier, order_lock),
            name=f"bot-{symbol}",
            daemon=True,
        )
        threads.append(t)
        t.start()
        print(f"[Live] Thread started for {symbol}")

    # Keep the main thread alive; threads are daemons so Ctrl-C exits cleanly
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n[Live] Shutting down ...")
        notifier.info("Bot stopped by user.")


# ---------------------------------------------------------------------------
# Monitor — position watcher
# ---------------------------------------------------------------------------

def run_monitor(args, config) -> None:
    """
    Periodically check all open positions and send a Telegram alert
    with unrealized PnL and available balance whenever positions exist.
    """
    interval = args.interval
    client   = BitgetClient(config.api_key, config.secret, config.passphrase)
    notifier = TelegramNotifier(config.telegram_token, config.telegram_chat_id)

    print(f"[Monitor] Started — checking every {interval}s. Press Ctrl-C to stop.")
    notifier.info(f"Position monitor started (interval: {interval}s)")

    while True:
        try:
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            positions = client.get_all_positions(config.product_type)
            open_pos  = [p for p in positions if float(p.get("total", 0)) != 0]

            if open_pos:
                account = client.get_account(config.margin_coin, config.product_type)
                balance = float(account.get("available", 0))

                print(f"\n[Monitor] [{now} UTC] {len(open_pos)} open position(s):")
                for p in open_pos:
                    upnl = p.get("unrealizedPL", "?")
                    print(
                        f"  {p.get('symbol')} {p.get('holdSide','?').upper()} "
                        f"x{p.get('leverage','?')} | size={p.get('total')} | "
                        f"entry={p.get('averageOpenPrice')} | mark={p.get('markPrice')} | "
                        f"uPnL={upnl}"
                    )
                print(f"  Available balance: {balance:.4f} USDT")

                notifier.position_update(open_pos, balance)
            else:
                print(f"[Monitor] [{now} UTC] No open positions.")

        except BitgetAPIError as exc:
            print(f"[Monitor] API error: {exc}")
            notifier.error_alert("Monitor", str(exc))
        except Exception as exc:
            print(f"[Monitor] Unexpected error: {exc}")
            notifier.error_alert("Monitor", str(exc))

        time.sleep(interval)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bitget RSI+MACD Futures Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live",     action="store_true", help="Run live trading loop")
    mode.add_argument("--backtest", action="store_true", help="Run backtesting engine")
    mode.add_argument("--monitor",  action="store_true", help="Watch open positions and alert via Telegram")

    # Symbol selection — --symbols takes priority over --symbol
    sym_group = parser.add_mutually_exclusive_group()
    sym_group.add_argument(
        "--symbols", type=str, default=None,
        metavar="SYM1,SYM2,...",
        help="Comma-separated list of symbols, e.g. BTCUSDT,ETHUSDT,SOLUSDT",
    )
    sym_group.add_argument(
        "--symbol", type=str, default=None,
        help="Single symbol (kept for backward compatibility)",
    )

    parser.add_argument("--tf",        type=str,   default=None,       help="Timeframe, e.g. 15m, 4H")
    parser.add_argument("--limit",     type=int,   default=1000,       help="Candles to fetch per symbol")
    parser.add_argument("--out-dir",   type=str,   default="backtest", help="Directory to save backtest charts")
    parser.add_argument("--balance",   type=float, default=10000.0,    help="Starting balance for backtest (USDT)")
    parser.add_argument("--interval",  type=int,   default=60,         help="Monitor check interval in seconds (default: 60)")
    parser.add_argument("--leverages", type=str,   default=None,
                        metavar="SYM=N,...",
                        help="Per-symbol leverage overrides, e.g. BTCUSDT=8,ETHUSDT=6,SOLUSDT=4")

    args = parser.parse_args()
    config = load_config()

    _needs_auth = args.live or args.monitor
    if _needs_auth:
        if not config.api_key or not config.secret or not config.passphrase:
            print("[Error] This mode requires BITGET_API_KEY, BITGET_SECRET, BITGET_PASSPHRASE in .env")
            sys.exit(1)

    if args.backtest:
        run_backtest(args, config)
    elif args.live:
        run_live(args, config)
    elif args.monitor:
        run_monitor(args, config)


if __name__ == "__main__":
    main()
