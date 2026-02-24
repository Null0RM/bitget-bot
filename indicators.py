from typing import Optional, Tuple
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


def calculate_macd(
    closes: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Return (macd_line, signal_line, histogram)."""
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def generate_signal(
    rsi: pd.Series,
    macd_line: pd.Series,
    signal_line: pd.Series,
    rsi_oversold: float = 30.0,
    rsi_overbought: float = 70.0,
    rsi_lookback: int = 5,
) -> Optional[str]:
    """
    Generate a trading signal using a short RSI lookback window.

    BUY:  RSI was below oversold within the last `rsi_lookback` bars
          AND MACD crosses above signal on the current bar.

    SELL: RSI was above overbought within the last `rsi_lookback` bars
          AND MACD crosses below signal on the current bar.

    The lookback window lets the MACD crossover (momentum confirmation)
    occur 1-N bars after the RSI extreme, which is how this setup is
    used in practice — RSI flags the exhaustion zone, MACD confirms the turn.

    Returns 'buy', 'sell', or None.
    """
    lookback = max(2, rsi_lookback + 1)
    if len(rsi) < lookback or len(macd_line) < 2:
        return None

    macd_curr = macd_line.iloc[-1]
    macd_prev = macd_line.iloc[-2]
    sig_curr = signal_line.iloc[-1]
    sig_prev = signal_line.iloc[-2]

    macd_crossed_up = macd_prev <= sig_prev and macd_curr > sig_curr
    macd_crossed_down = macd_prev >= sig_prev and macd_curr < sig_curr

    # RSI condition: was extreme within the lookback window
    rsi_window = rsi.iloc[-rsi_lookback:]
    rsi_was_oversold = bool((rsi_window < rsi_oversold).any())
    rsi_was_overbought = bool((rsi_window > rsi_overbought).any())

    if rsi_was_oversold and macd_crossed_up:
        return "buy"
    if rsi_was_overbought and macd_crossed_down:
        return "sell"
    return None
