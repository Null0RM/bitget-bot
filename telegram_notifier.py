import requests


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self._base_url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._enabled = bool(token and chat_id)

    def send(self, message: str) -> None:
        """Fire-and-forget message send. Silently catches errors."""
        if not self._enabled:
            return
        try:
            requests.post(
                self._base_url,
                json={"chat_id": self.chat_id, "text": message, "parse_mode": "Markdown"},
                timeout=5,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[Telegram] Failed to send message: {exc}")

    def trade_opened(
        self,
        symbol: str,
        side: str,
        entry: float,
        size: float,
        sl: float,
        tp: float,
        rsi: float,
        ema_fast: float,
        ema_slow: float,
    ) -> None:
        icon = "🟢" if side.lower() == "buy" else "🔴"
        msg = (
            f"{icon} *Trade Opened*\n"
            f"Symbol: `{symbol}`\n"
            f"Side: `{side.upper()}`\n"
            f"Entry: `{entry}`\n"
            f"Size: `{size}`\n"
            f"Stop-Loss: `{sl}`\n"
            f"Take-Profit: `{tp}`\n"
            f"RSI: `{rsi:.2f}` | EMA9: `{ema_fast:.4f}` | EMA21: `{ema_slow:.4f}`"
        )
        self.send(msg)

    def trade_closed(self, symbol: str, side: str, pnl: float) -> None:
        icon = "✅" if pnl >= 0 else "❌"
        msg = (
            f"{icon} *Trade Closed*\n"
            f"Symbol: `{symbol}`\n"
            f"Side: `{side.upper()}`\n"
            f"PnL: `{pnl:+.4f} USDT`"
        )
        self.send(msg)

    def error_alert(self, context: str, error: str) -> None:
        msg = (
            f"⚠️ *Bot Error*\n"
            f"Context: `{context}`\n"
            f"Error: `{error}`"
        )
        self.send(msg)

    def info(self, message: str) -> None:
        self.send(f"ℹ️ {message}")
