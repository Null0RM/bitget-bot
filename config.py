from dataclasses import dataclass, field
from dotenv import load_dotenv
import os

load_dotenv()


@dataclass
class Config:
    # Bitget credentials
    api_key: str = field(default_factory=lambda: os.getenv("BITGET_API_KEY", ""))
    secret: str = field(default_factory=lambda: os.getenv("BITGET_SECRET", ""))
    passphrase: str = field(default_factory=lambda: os.getenv("BITGET_PASSPHRASE", ""))

    # Telegram
    telegram_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))

    # Trading parameters
    symbol: str = field(default_factory=lambda: os.getenv("SYMBOL", "BTCUSDT"))
    product_type: str = field(default_factory=lambda: os.getenv("PRODUCT_TYPE", "USDT-FUTURES"))
    margin_coin: str = field(default_factory=lambda: os.getenv("MARGIN_COIN", "USDT"))
    timeframe: str = field(default_factory=lambda: os.getenv("TIMEFRAME", "15m"))
    leverage: int = field(default_factory=lambda: int(os.getenv("LEVERAGE", "5")))

    # Risk management
    collateral_pct: float = field(default_factory=lambda: float(os.getenv("COLLATERAL_PCT", "10.0")))
    sl_pct: float = field(default_factory=lambda: float(os.getenv("SL_PCT", "2.0")))
    tp_pct: float = field(default_factory=lambda: float(os.getenv("TP_PCT", "4.0")))

    # Trend direction
    ema_trend: int = field(default_factory=lambda: int(os.getenv("EMA_TREND", "50")))

    # Support / Resistance detection
    sr_lookback: int = field(default_factory=lambda: int(os.getenv("SR_LOOKBACK", "100")))
    sr_swing_n: int = field(default_factory=lambda: int(os.getenv("SR_SWING_N", "3")))
    sr_touch_tolerance: float = field(default_factory=lambda: float(os.getenv("SR_TOUCH_TOLERANCE", "0.015")))
    sr_proximity: float = field(default_factory=lambda: float(os.getenv("SR_PROXIMITY", "0.02")))
    sr_min_touches: int = field(default_factory=lambda: int(os.getenv("SR_MIN_TOUCHES", "2")))


def load_config() -> Config:
    return Config()
