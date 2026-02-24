from typing import Optional
import pandas as pd
import numpy as np


def calculate_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    """Compute RSI using Wilder's smoothing method."""
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_ema(closes: pd.Series, period: int) -> pd.Series:
    """Exponential moving average."""
    return closes.ewm(span=period, adjust=False).mean()


def generate_signal(
    closes: pd.Series,
    rsi: pd.Series,
    ema_fast: pd.Series,
    ema_slow: pd.Series,
    ema_trend: pd.Series,
    rsi_long_min: float = 45.0,
    rsi_long_max: float = 70.0,
    rsi_short_min: float = 30.0,
    rsi_short_max: float = 55.0,
) -> Optional[str]:
    """
    EMA crossover strategy with trend filter and RSI momentum confirmation.

    Long  (buy):  EMA_fast crosses above EMA_slow
                  AND price > EMA_trend  (confirmed uptrend)
                  AND RSI in [rsi_long_min, rsi_long_max]  (momentum up, not overbought)

    Short (sell): EMA_fast crosses below EMA_slow
                  AND price < EMA_trend  (confirmed downtrend)
                  AND RSI in [rsi_short_min, rsi_short_max]  (momentum down, not oversold)

    Returns 'buy', 'sell', or None.
    """
    if len(ema_fast) < 2:
        return None

    prev_fast, curr_fast = float(ema_fast.iloc[-2]), float(ema_fast.iloc[-1])
    prev_slow, curr_slow = float(ema_slow.iloc[-2]), float(ema_slow.iloc[-1])
    curr_trend = float(ema_trend.iloc[-1])
    curr_price = float(closes.iloc[-1])
    curr_rsi = float(rsi.iloc[-1])

    if pd.isna(curr_rsi) or pd.isna(curr_trend):
        return None

    crossed_up   = prev_fast <= prev_slow and curr_fast > curr_slow
    crossed_down = prev_fast >= prev_slow and curr_fast < curr_slow

    if crossed_up and curr_price > curr_trend and rsi_long_min <= curr_rsi <= rsi_long_max:
        return "buy"
    if crossed_down and curr_price < curr_trend and rsi_short_min <= curr_rsi <= rsi_short_max:
        return "sell"
    return None
