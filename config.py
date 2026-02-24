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
    risk_pct: float = field(default_factory=lambda: float(os.getenv("RISK_PCT", "1.0")))
    sl_pct: float = field(default_factory=lambda: float(os.getenv("SL_PCT", "2.0")))
    tp_pct: float = field(default_factory=lambda: float(os.getenv("TP_PCT", "4.0")))

    # RSI parameters
    rsi_period: int = field(default_factory=lambda: int(os.getenv("RSI_PERIOD", "14")))
    rsi_oversold: float = field(default_factory=lambda: float(os.getenv("RSI_OVERSOLD", "30")))
    rsi_overbought: float = field(default_factory=lambda: float(os.getenv("RSI_OVERBOUGHT", "70")))
    rsi_lookback: int = field(default_factory=lambda: int(os.getenv("RSI_LOOKBACK", "5")))

    # MACD parameters
    macd_fast: int = field(default_factory=lambda: int(os.getenv("MACD_FAST", "12")))
    macd_slow: int = field(default_factory=lambda: int(os.getenv("MACD_SLOW", "26")))
    macd_signal: int = field(default_factory=lambda: int(os.getenv("MACD_SIGNAL", "9")))


def load_config() -> Config:
    return Config()
