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

    # RSI parameters (used as momentum filter, not reversal signal)
    rsi_period: int = field(default_factory=lambda: int(os.getenv("RSI_PERIOD", "14")))
    rsi_long_min: float = field(default_factory=lambda: float(os.getenv("RSI_LONG_MIN", "45.0")))
    rsi_long_max: float = field(default_factory=lambda: float(os.getenv("RSI_LONG_MAX", "70.0")))
    rsi_short_min: float = field(default_factory=lambda: float(os.getenv("RSI_SHORT_MIN", "30.0")))
    rsi_short_max: float = field(default_factory=lambda: float(os.getenv("RSI_SHORT_MAX", "55.0")))

    # EMA parameters
    ema_fast: int = field(default_factory=lambda: int(os.getenv("EMA_FAST", "9")))
    ema_slow: int = field(default_factory=lambda: int(os.getenv("EMA_SLOW", "21")))
    ema_trend: int = field(default_factory=lambda: int(os.getenv("EMA_TREND", "50")))


def load_config() -> Config:
    return Config()
