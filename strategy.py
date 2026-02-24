from typing import Optional
import pandas as pd

from indicators import calculate_rsi, calculate_macd, generate_signal
from config import Config


class RSIMACDStrategy:
    def __init__(self, config: Config):
        self.config = config

    def get_signal(self, df: pd.DataFrame) -> Optional[dict]:
        """
        Analyse the OHLCV DataFrame and return a signal dict or None.

        Expected DataFrame columns: open, high, low, close, volume.

        Returns:
            {
                "side": "buy" | "sell",
                "entry_price": float,   # last close
                "rsi": float,
                "macd": float,
                "macd_signal": float,
            }
            or None if no signal.
        """
        if len(df) < self.config.macd_slow + self.config.macd_signal + 5:
            return None

        closes = df["close"].astype(float)

        rsi = calculate_rsi(closes, self.config.rsi_period)
        macd_line, signal_line, _ = calculate_macd(
            closes,
            self.config.macd_fast,
            self.config.macd_slow,
            self.config.macd_signal,
        )

        side = generate_signal(
            rsi,
            macd_line,
            signal_line,
            self.config.rsi_oversold,
            self.config.rsi_overbought,
            self.config.rsi_lookback,
        )

        if side is None:
            return None

        return {
            "side": side,
            "entry_price": float(closes.iloc[-1]),
            "rsi": float(rsi.iloc[-1]),
            "macd": float(macd_line.iloc[-1]),
            "macd_signal": float(signal_line.iloc[-1]),
        }
