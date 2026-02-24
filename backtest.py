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
) -> None:
    """Generate and save a two-panel chart: price+trades and equity curve."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), sharex=False)
    fig.patch.set_facecolor("#1a1a2e")
    for ax in (ax1, ax2):
        ax.set_facecolor("#16213e")
        ax.tick_params(colors="white")
        ax.spines["bottom"].set_color("#444")
        ax.spines["top"].set_color("#444")
        ax.spines["left"].set_color("#444")
        ax.spines["right"].set_color("#444")
        ax.yaxis.label.set_color("white")
        ax.xaxis.label.set_color("white")
        ax.title.set_color("white")

    # ---- Price chart ----
    bars = range(len(df))
    closes = df["close"].astype(float).values
    ax1.plot(bars, closes, color="#4fc3f7", linewidth=1, label="Close")

    for trade in trades:
        color = "#00e676" if trade.side == "buy" else "#ff1744"
        ax1.axvline(x=trade.entry_bar, color=color, alpha=0.4, linewidth=0.8)
        if trade.exit_bar is not None:
            ax1.axvline(x=trade.exit_bar, color=color, alpha=0.2, linewidth=0.5)
        marker = "^" if trade.side == "buy" else "v"
        ax1.scatter(trade.entry_bar, trade.entry_price, marker=marker, color=color, s=60, zorder=5)

    ax1.set_title("Price + Trades")
    ax1.set_ylabel("Price (USDT)")
    ax1.legend(facecolor="#16213e", labelcolor="white")
    ax1.grid(color="#2a2a4a", linewidth=0.5)

    # ---- Equity curve ----
    eq_bars = range(len(equity))
    ax2.plot(eq_bars, equity, color="#ffd54f", linewidth=1.5)
    ax2.fill_between(eq_bars, equity, min(equity), alpha=0.2, color="#ffd54f")
    ax2.set_title("Equity Curve")
    ax2.set_ylabel("Balance (USDT)")
    ax2.set_xlabel("Bar")
    ax2.grid(color="#2a2a4a", linewidth=0.5)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[Backtest] Chart saved to {output_path}")
