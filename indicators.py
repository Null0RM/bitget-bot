from typing import Optional, Tuple, List
import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Trend
# ---------------------------------------------------------------------------

def calculate_ema(closes: pd.Series, period: int) -> pd.Series:
    """Exponential moving average."""
    return closes.ewm(span=period, adjust=False).mean()


# ---------------------------------------------------------------------------
# Support / Resistance
# ---------------------------------------------------------------------------

def find_sr_levels(
    df: pd.DataFrame,
    lookback: int = 100,
    swing_n: int = 3,
    tolerance: float = 0.015,
    min_touches: int = 2,
) -> Tuple[List[float], List[float]]:
    """
    Detect support and resistance levels from recent swing highs/lows.

    Algorithm:
    1. Scan the last `lookback` bars for swing highs and lows.
       A swing high at bar i: high[i] is the maximum in window [i-n, i+n].
       A swing low at bar i:  low[i]  is the minimum in window [i-n, i+n].
    2. Cluster nearby swings (within `tolerance`%) into single levels.
    3. Count how many bars came within `tolerance`% of each clustered level.
    4. Keep only levels with >= `min_touches` touches.

    Returns (supports, resistances) — lists of price levels.
    """
    window = df.iloc[-lookback:] if len(df) > lookback else df
    highs  = window["high"].astype(float).values
    lows   = window["low"].astype(float).values
    n      = len(window)

    swing_highs: List[float] = []
    swing_lows:  List[float] = []

    for i in range(swing_n, n - swing_n):
        hi_win = highs[i - swing_n: i + swing_n + 1]
        lo_win = lows [i - swing_n: i + swing_n + 1]
        if highs[i] == hi_win.max():
            swing_highs.append(float(highs[i]))
        if lows[i] == lo_win.min():
            swing_lows.append(float(lows[i]))

    def cluster(raw: List[float]) -> List[float]:
        if not raw:
            return []
        raw_sorted = sorted(set(raw))
        used   = [False] * len(raw_sorted)
        result = []
        for i, base in enumerate(raw_sorted):
            if used[i]:
                continue
            group = [base]
            for j in range(i + 1, len(raw_sorted)):
                if not used[j] and abs(raw_sorted[j] - base) / base <= tolerance:
                    group.append(raw_sorted[j])
                    used[j] = True
            used[i] = True
            center = float(np.mean(group))
            # Count bars that came within tolerance of this level
            touches = int(np.sum(
                (np.abs(highs - center) / center <= tolerance) |
                (np.abs(lows  - center) / center <= tolerance)
            ))
            if touches >= min_touches:
                result.append(center)
        return result

    supports    = cluster(swing_lows)
    resistances = cluster(swing_highs)
    return supports, resistances


# ---------------------------------------------------------------------------
# Price action — candlestick patterns
# ---------------------------------------------------------------------------

def detect_candle_pattern(df: pd.DataFrame) -> Optional[str]:
    """
    Detect the pattern on the most recent bar.

    Patterns recognised:
      bullish_engulfing — prev bar bearish, current bar bullish body fully engulfs prev body
      bearish_engulfing — prev bar bullish, current bar bearish body fully engulfs prev body
      hammer            — small body at top, long lower wick (≥ 2× body), upward-close
      shooting_star     — small body at bottom, long upper wick (≥ 2× body), downward-close
      doji              — open ≈ close (body ≤ 10% of total range)

    Returns the pattern name or None.
    """
    if len(df) < 2:
        return None

    curr = df.iloc[-1]
    prev = df.iloc[-2]

    c_o, c_c = float(curr["open"]), float(curr["close"])
    c_h, c_l = float(curr["high"]), float(curr["low"])
    p_o, p_c = float(prev["open"]), float(prev["close"])

    c_body  = abs(c_c - c_o)
    c_range = c_h - c_l
    if c_range < 1e-10:
        return None

    c_upper = c_h - max(c_o, c_c)   # wick above body
    c_lower = min(c_o, c_c) - c_l   # wick below body

    # ---- Engulfing ----
    if p_c < p_o and c_c > c_o:           # prev bearish, curr bullish
        if c_o <= p_c and c_c >= p_o:     # curr body wraps around prev body
            return "bullish_engulfing"

    if p_c > p_o and c_c < c_o:           # prev bullish, curr bearish
        if c_o >= p_c and c_c <= p_o:     # curr body wraps around prev body
            return "bearish_engulfing"

    # ---- Hammer (bullish reversal at support) ----
    # Small real body, long lower wick, little or no upper wick
    if (c_body <= c_range * 0.35 and
            c_lower >= c_body * 2.0 and
            c_upper <= c_body):
        return "hammer"

    # ---- Shooting Star (bearish reversal at resistance) ----
    # Small real body, long upper wick, little or no lower wick
    if (c_body <= c_range * 0.35 and
            c_upper >= c_body * 2.0 and
            c_lower <= c_body):
        return "shooting_star"

    # ---- Doji (indecision — valid reversal at key S/R) ----
    if c_body <= c_range * 0.1:
        return "doji"

    return None


# ---------------------------------------------------------------------------
# Signal generation
# ---------------------------------------------------------------------------

_BULLISH_PATTERNS = {"bullish_engulfing", "hammer", "doji"}
_BEARISH_PATTERNS = {"bearish_engulfing", "shooting_star", "doji"}

_PATTERN_SHORT = {
    "bullish_engulfing": "BullEng",
    "bearish_engulfing": "BearEng",
    "hammer":            "Hammer",
    "shooting_star":     "ShootStar",
    "doji":              "Doji",
}


def generate_signal(df: pd.DataFrame, config) -> Optional[Tuple]:
    """
    Holistic signal requiring all three pillars to align:

      BUY:  price above EMA_trend (uptrend)
            AND price within sr_proximity% of a support level
            AND bullish candlestick pattern on the current bar

      SELL: price below EMA_trend (downtrend)
            AND price within sr_proximity% of a resistance level
            AND bearish candlestick pattern on the current bar

    Returns (side, pattern, supports, resistances) or None.
    """
    closes = df["close"].astype(float)
    trend_ema  = calculate_ema(closes, config.ema_trend)
    curr_price = float(closes.iloc[-1])
    curr_ema   = float(trend_ema.iloc[-1])

    if pd.isna(curr_ema):
        return None

    trend = "up" if curr_price > curr_ema else "down"

    supports, resistances = find_sr_levels(
        df,
        lookback=config.sr_lookback,
        swing_n=config.sr_swing_n,
        tolerance=config.sr_touch_tolerance,
        min_touches=config.sr_min_touches,
    )

    pattern = detect_candle_pattern(df)

    prox            = config.sr_proximity
    near_support    = any(abs(curr_price - lvl) / lvl <= prox for lvl in supports)
    near_resistance = any(abs(curr_price - lvl) / lvl <= prox for lvl in resistances)

    if trend == "up" and near_support and pattern in _BULLISH_PATTERNS:
        return "buy", pattern, supports, resistances

    if trend == "down" and near_resistance and pattern in _BEARISH_PATTERNS:
        return "sell", pattern, supports, resistances

    return None
