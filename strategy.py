from typing import Optional
import pandas as pd

from indicators import generate_signal
from config import Config


class HolisticStrategy:
    """
    Three-pillar trading strategy:
      1. Trend direction  — price relative to EMA(ema_trend)
      2. Horizontal S/R   — swing-based support/resistance levels
      3. Price action     — candlestick pattern confirmation

    A signal fires only when all three pillars align on the same bar.
    """

    def __init__(self, config: Config):
        self.config = config

    def get_signal(self, df: pd.DataFrame) -> Optional[dict]:
        """
        Analyse the OHLCV DataFrame and return a signal dict or None.

        Minimum bars required: sr_lookback + sr_swing_n + 5
        (ensures enough history to detect meaningful S/R levels)

        Returns:
            {
                "side":         "buy" | "sell",
                "entry_price":  float,
                "pattern":      str,          # pattern that confirmed the signal
                "supports":     list[float],  # active support levels
                "resistances":  list[float],  # active resistance levels
            }
            or None if no signal.
        """
        min_bars = self.config.sr_lookback + self.config.sr_swing_n + 5
        if len(df) < min_bars:
            return None

        result = generate_signal(df, self.config)
        if result is None:
            return None

        side, pattern, supports, resistances = result
        closes = df["close"].astype(float)

        return {
            "side":         side,
            "entry_price":  float(closes.iloc[-1]),
            "pattern":      pattern,
            "supports":     supports,
            "resistances":  resistances,
        }
