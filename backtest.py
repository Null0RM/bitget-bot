from dataclasses import dataclass, field
from typing import List, Optional
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from config import Config
from strategy import EMATrendStrategy
from risk_manager import RiskManager


@dataclass
class Trade:
    entry_bar: int
    entry_price: float
    side: str          # 'buy' or 'sell'
    size: float
    sl_price: float
    tp_price: float
    exit_bar: Optional[int] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # 'sl', 'tp', 'end'
    pnl: float = 0.0


class BacktestEngine:
    def __init__(self):
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []

    def run(
        self,
        df: pd.DataFrame,
        strategy: EMATrendStrategy,
        risk_manager: RiskManager,
        config: Config,
        initial_balance: float = 10_000.0,
    ) -> dict:
        """
        Simulate bar-by-bar trading.

        df must have columns: open, high, low, close, volume
        indexed 0..N-1.
        """
        df = df.reset_index(drop=True)
        balance = initial_balance
        self.equity_curve = [balance]
        self.trades = []
        open_trade: Optional[Trade] = None

        min_bars = config.ema_trend + 5

        for i in range(1, len(df)):
            bar = df.iloc[i]
            high = float(bar["high"])
            low = float(bar["low"])
            close = float(bar["close"])

            # ---- check if existing trade hit SL or TP ----
            if open_trade is not None:
                hit_sl = hit_tp = False

                if open_trade.side == "buy":
                    hit_sl = low <= open_trade.sl_price
                    hit_tp = high >= open_trade.tp_price
                else:
                    hit_sl = high >= open_trade.sl_price
                    hit_tp = low <= open_trade.tp_price

                if hit_tp and hit_sl:
                    # Conservative: assume SL hit first
                    hit_sl, hit_tp = True, False

                if hit_sl or hit_tp:
                    exit_price = open_trade.sl_price if hit_sl else open_trade.tp_price
                    reason = "sl" if hit_sl else "tp"
                    pnl = self._calc_pnl(open_trade, exit_price, config.leverage)
                    balance += pnl
                    open_trade.exit_bar = i
                    open_trade.exit_price = exit_price
                    open_trade.exit_reason = reason
                    open_trade.pnl = pnl
                    self.trades.append(open_trade)
                    open_trade = None

            # ---- generate signal from history up to bar i ----
            if open_trade is None and i >= min_bars:
                window = df.iloc[: i + 1]
                signal = strategy.get_signal(window)

                if signal is not None:
                    entry = close
                    size = risk_manager.calculate_position_size(balance, entry)
                    sl_price, tp_price = risk_manager.calculate_sl_tp(entry, signal["side"])
                    open_trade = Trade(
                        entry_bar=i,
                        entry_price=entry,
                        side=signal["side"],
                        size=size,
                        sl_price=sl_price,
                        tp_price=tp_price,
                    )

            self.equity_curve.append(balance)

        # Close any remaining open trade at last close
        if open_trade is not None:
            last_close = float(df.iloc[-1]["close"])
            pnl = self._calc_pnl(open_trade, last_close, config.leverage)
            balance += pnl
            open_trade.exit_bar = len(df) - 1
            open_trade.exit_price = last_close
            open_trade.exit_reason = "end"
            open_trade.pnl = pnl
            self.trades.append(open_trade)
            self.equity_curve[-1] = balance

        return self._metrics(initial_balance, balance)

    @staticmethod
    def _calc_pnl(trade: Trade, exit_price: float, leverage: int) -> float:
        # size is the notional quantity; P&L = size * price_change (no leverage factor).
        # Leverage is already reflected in the position size chosen by the risk manager.
        if trade.side == "buy":
            return trade.size * (exit_price - trade.entry_price)
        else:
            return trade.size * (trade.entry_price - exit_price)

    def _metrics(self, initial: float, final: float) -> dict:
        num_trades = len(self.trades)
        if num_trades == 0:
            return {
                "num_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "final_balance": final,
            }

        wins = sum(1 for t in self.trades if t.pnl > 0)
        win_rate = wins / num_trades * 100
        total_pnl = final - initial

        equity = np.array(self.equity_curve, dtype=float)
        peak = np.maximum.accumulate(equity)
        drawdowns = (peak - equity) / peak
        max_drawdown = float(drawdowns.max() * 100)

        returns = np.diff(equity) / equity[:-1]
        sharpe = 0.0
        if returns.std() > 0:
            sharpe = float((returns.mean() / returns.std()) * np.sqrt(252))

        return {
            "num_trades": num_trades,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 4),
            "max_drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe, 4),
            "final_balance": round(final, 4),
        }


def plot_results(
    df: pd.DataFrame,
    trades: List[Trade],
    equity: List[float],
    output_path: str = "backtest_results.png",
    config=None,
) -> None:
    """
    Generate and save a three-panel chart:
      1. Price + EMA lines + trade markers (entry ▲/▼, exit ★TP / ✕SL / ○end)
      2. Equity curve with drawdown fill
      3. Per-trade PnL bar chart
    """
    closes = df["close"].astype(float)
    ema_fast_p  = config.ema_fast  if config else 9
    ema_slow_p  = config.ema_slow  if config else 21
    ema_trend_p = config.ema_trend if config else 50
    ema_fast_v  = closes.ewm(span=ema_fast_p,  adjust=False).mean().values
    ema_slow_v  = closes.ewm(span=ema_slow_p,  adjust=False).mean().values
    ema_trend_v = closes.ewm(span=ema_trend_p, adjust=False).mean().values

    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1, figsize=(20, 14),
        gridspec_kw={"height_ratios": [3, 1.5, 1]},
    )
    fig.patch.set_facecolor("#1a1a2e")
    for ax in (ax1, ax2, ax3):
        ax.set_facecolor("#16213e")
        ax.tick_params(colors="white")
        for spine in ax.spines.values():
            spine.set_color("#444")
        ax.yaxis.label.set_color("white")
        ax.xaxis.label.set_color("white")
        ax.title.set_color("white")

    bars = range(len(df))
    closes_arr = closes.values

    # ------------------------------------------------------------------ #
    # Panel 1 — Price + EMAs + trade markers
    # ------------------------------------------------------------------ #
    ax1.plot(bars, closes_arr, color="#4fc3f7", linewidth=1,   label="Close",                    alpha=0.8)
    ax1.plot(bars, ema_fast_v, color="#00e5ff", linewidth=1.2, label=f"EMA{ema_fast_p}",         alpha=0.9)
    ax1.plot(bars, ema_slow_v, color="#ff9800", linewidth=1.2, label=f"EMA{ema_slow_p}",         alpha=0.9)
    ax1.plot(bars, ema_trend_v,color="#ce93d8", linewidth=1.5, label=f"EMA{ema_trend_p} (trend)", alpha=0.9)

    # Outcome colours
    _CLR = {"tp": "#00e676", "sl": "#ff1744", "end": "#ffd54f"}
    _EXIT_MARKER = {"tp": "*", "sl": "X", "end": "o"}

    for trade in trades:
        outcome   = trade.exit_reason or "end"
        clr       = _CLR.get(outcome, "#ffffff")
        entry_clr = "#00e676" if trade.side == "buy" else "#ff1744"
        entry_mkr = "^"       if trade.side == "buy" else "v"

        # Shaded region spanning the trade duration
        if trade.exit_bar is not None:
            ax1.axvspan(trade.entry_bar, trade.exit_bar, alpha=0.08, color=clr)

        # Entry marker
        ax1.scatter(trade.entry_bar, trade.entry_price,
                    marker=entry_mkr, color=entry_clr, s=90, zorder=6)

        # Exit marker + dashed connector
        if trade.exit_bar is not None and trade.exit_price is not None:
            ax1.scatter(trade.exit_bar, trade.exit_price,
                        marker=_EXIT_MARKER.get(outcome, "o"),
                        color=clr, s=110, zorder=6)
            ax1.plot([trade.entry_bar, trade.exit_bar],
                     [trade.entry_price, trade.exit_price],
                     color=clr, linewidth=0.8, linestyle="--", alpha=0.5)

    # Legend for outcome markers (proxy artists)
    from matplotlib.lines import Line2D
    legend_extra = [
        Line2D([0], [0], marker="^", color="w", markerfacecolor="#00e676", markersize=8, label="Long entry",  linestyle="None"),
        Line2D([0], [0], marker="v", color="w", markerfacecolor="#ff1744", markersize=8, label="Short entry", linestyle="None"),
        Line2D([0], [0], marker="*", color="w", markerfacecolor="#00e676", markersize=10, label="TP exit",    linestyle="None"),
        Line2D([0], [0], marker="X", color="w", markerfacecolor="#ff1744", markersize=8,  label="SL exit",    linestyle="None"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#ffd54f", markersize=8,  label="End exit",   linestyle="None"),
    ]
    handles, labels = ax1.get_legend_handles_labels()
    ax1.legend(handles + legend_extra, labels + [h.get_label() for h in legend_extra],
               facecolor="#16213e", labelcolor="white", fontsize=8,
               loc="upper left", ncol=2)
    ax1.set_title("Price + EMAs + Trades")
    ax1.set_ylabel("Price (USDT)")
    ax1.grid(color="#2a2a4a", linewidth=0.5)

    # ------------------------------------------------------------------ #
    # Panel 2 — Equity curve with drawdown shading
    # ------------------------------------------------------------------ #
    eq_arr  = np.array(equity, dtype=float)
    eq_bars = range(len(eq_arr))
    peak    = np.maximum.accumulate(eq_arr)

    ax2.plot(eq_bars, eq_arr,  color="#ffd54f", linewidth=1.5, label="Balance")
    ax2.plot(eq_bars, peak,    color="#888888", linewidth=0.8, linestyle="--", label="Peak")
    ax2.fill_between(eq_bars, eq_arr, peak, alpha=0.25, color="#ff1744", label="Drawdown")
    ax2.fill_between(eq_bars, eq_arr, eq_arr[0], where=eq_arr >= eq_arr[0],
                     alpha=0.15, color="#00e676")
    ax2.set_title("Equity Curve")
    ax2.set_ylabel("Balance (USDT)")
    ax2.legend(facecolor="#16213e", labelcolor="white", fontsize=8)
    ax2.grid(color="#2a2a4a", linewidth=0.5)

    # ------------------------------------------------------------------ #
    # Panel 3 — Per-trade PnL bars
    # ------------------------------------------------------------------ #
    if trades:
        pnls   = [t.pnl for t in trades]
        clrs   = [_CLR.get(t.exit_reason or "end", "#ffd54f") for t in trades]
        x_pos  = range(len(pnls))
        ax3.bar(x_pos, pnls, color=clrs, alpha=0.85, width=0.6)
        ax3.axhline(0, color="#888888", linewidth=0.8)

        # Label each bar with TP / SL / END
        y_max = max(abs(p) for p in pnls) if pnls else 1
        for i, trade in enumerate(trades):
            label = (trade.exit_reason or "end").upper()
            offset = y_max * 0.06
            va = "bottom" if trade.pnl >= 0 else "top"
            y  = trade.pnl + offset if trade.pnl >= 0 else trade.pnl - offset
            ax3.text(i, y, label, ha="center", va=va, color="white", fontsize=7)

        ax3.set_title("Per-Trade PnL")
        ax3.set_ylabel("PnL (USDT)")
        ax3.set_xlabel("Trade #")
        ax3.grid(color="#2a2a4a", linewidth=0.5, axis="y")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[Backtest] Chart saved to {output_path}")
