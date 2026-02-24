from typing import Optional
import pandas as pd

from indicators import calculate_rsi, calculate_ema, generate_signal
from config import Config


class EMATrendStrategy:
    def __init__(self, config: Config):
        self.config = config

    def get_signal(self, df: pd.DataFrame) -> Optional[dict]:
        """
        Analyse the OHLCV DataFrame and return a signal dict or None.

        Expected DataFrame columns: open, high, low, close, volume.

        Returns:
            {
                "side":        "buy" | "sell",
                "entry_price": float,   # last close
                "rsi":         float,
                "ema_fast":    float,
                "ema_slow":    float,
            }
            or None if no signal.
        """
        if len(df) < self.config.ema_trend + 5:
            return None

        closes = df["close"].astype(float)

        rsi       = calculate_rsi(closes, self.config.rsi_period)
        ema_fast  = calculate_ema(closes, self.config.ema_fast)
        ema_slow  = calculate_ema(closes, self.config.ema_slow)
        ema_trend = calculate_ema(closes, self.config.ema_trend)

        side = generate_signal(
            closes,
            rsi,
            ema_fast,
            ema_slow,
            ema_trend,
            self.config.rsi_long_min,
            self.config.rsi_long_max,
            self.config.rsi_short_min,
            self.config.rsi_short_max,
        )

        if side is None:
            return None

        return {
            "side":        side,
            "entry_price": float(closes.iloc[-1]),
            "rsi":         float(rsi.iloc[-1]),
            "ema_fast":    float(ema_fast.iloc[-1]),
            "ema_slow":    float(ema_slow.iloc[-1]),
        }
