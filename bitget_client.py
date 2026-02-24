import hashlib
import hmac
import base64
import time
import json
from typing import Any, Optional
import requests

BASE_URL = "https://api.bitget.com"

# Map human-readable timeframes to Bitget granularity strings
TIMEFRAME_MAP = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1H": "1H",
    "4H": "4H",
    "6H": "6H",
    "12H": "12H",
    "1D": "1D",
    "1W": "1W",
    "1M": "1M",
}


class BitgetAPIError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"Bitget API error {code}: {message}")


class BitgetClient:
    def __init__(self, api_key: str, secret: str, passphrase: str):
        self.api_key = api_key
        self.secret = secret
        self.passphrase = passphrase
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def _sign(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        prehash = timestamp + method.upper() + path + body
        mac = hmac.new(
            self.secret.encode("utf-8"),
            prehash.encode("utf-8"),
            hashlib.sha256,
        )
        return base64.b64encode(mac.digest()).decode()

    def _headers(self, method: str, path: str, body: str = "") -> dict:
        timestamp = str(int(time.time() * 1000))
        signature = self._sign(timestamp, method, path, body)
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Raw request
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
    ) -> Any:
        url = BASE_URL + path
        body = ""
        if data:
            body = json.dumps(data)

        # Build full path with query string for signing
        if params:
            query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
            sign_path = f"{path}?{query}"
        else:
            sign_path = path

        headers = self._headers(method, sign_path, body)

        resp = self.session.request(
            method,
            url,
            headers=headers,
            params=params,
            data=body if body else None,
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()

        if result.get("code") not in ("00000", 0, "0"):
            raise BitgetAPIError(result.get("code", "unknown"), result.get("msg", ""))

        return result.get("data")

    # ------------------------------------------------------------------
    # Public market data (no auth required for candles)
    # ------------------------------------------------------------------

    # Milliseconds per candle for each granularity (used for pagination)
    _TF_MS = {
        "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
        "30m": 1_800_000, "1H": 3_600_000, "4H": 14_400_000,
        "6H": 21_600_000, "12H": 43_200_000, "1D": 86_400_000,
        "1W": 604_800_000,
    }
    _PAGE_SIZE = 1000  # Bitget hard cap per request

    def _fetch_candles_page(
        self, symbol: str, gran: str, end_time_ms: Optional[int] = None
    ) -> list:
        """Fetch one page (≤1000 bars) ending at end_time_ms (exclusive)."""
        params: dict = {
            "symbol": symbol,
            "granularity": gran,
            "limit": str(self._PAGE_SIZE),
            "productType": "USDT-FUTURES",
        }
        if end_time_ms is not None:
            params["endTime"] = str(end_time_ms)

        url = BASE_URL + "/api/v2/mix/market/candles"
        resp = self.session.get(url, params=params, timeout=10)
        resp.raise_for_status()
        result = resp.json()

        if result.get("code") not in ("00000", 0, "0"):
            raise BitgetAPIError(result.get("code", "unknown"), result.get("msg", ""))

        raw = result.get("data", []) or []
        candles = []
        for row in raw:
            candles.append(
                {
                    "ts": int(row[0]),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                }
            )
        return candles

    def get_candles(self, symbol: str, granularity: str, limit: int = 200) -> list:
        """
        Return OHLCV candles sorted ascending by timestamp.

        Transparently paginates when limit > 1000 by walking backwards in
        time using the endTime parameter, then reassembling in order.
        """
        gran = TIMEFRAME_MAP.get(granularity, granularity)
        tf_ms = self._TF_MS.get(granularity, self._TF_MS.get(gran, 3_600_000))

        if limit <= self._PAGE_SIZE:
            candles = self._fetch_candles_page(symbol, gran)
            candles.sort(key=lambda x: x["ts"])
            return candles[-limit:] if len(candles) > limit else candles

        # Paginate: fetch from newest backwards until we have enough bars
        all_candles: dict[int, dict] = {}
        end_time_ms: Optional[int] = None

        while len(all_candles) < limit:
            page = self._fetch_candles_page(symbol, gran, end_time_ms)
            if not page:
                break
            for c in page:
                all_candles[c["ts"]] = c
            # Next page ends just before the oldest bar in this page
            oldest_ts = min(c["ts"] for c in page)
            end_time_ms = oldest_ts  # Bitget endTime is exclusive
            if len(page) < self._PAGE_SIZE:
                break  # no more history available

        result = sorted(all_candles.values(), key=lambda x: x["ts"])
        return result[-limit:] if len(result) > limit else result

    # ------------------------------------------------------------------
    # Authenticated endpoints
    # ------------------------------------------------------------------

    def get_account(self, margin_coin: str = "USDT", product_type: str = "USDT-FUTURES") -> dict:
        """Return account info including available balance."""
        params = {"marginCoin": margin_coin, "productType": product_type}
        return self._request("GET", "/api/v2/mix/account/account", params=params)

    def get_positions(self, symbol: str, product_type: str = "USDT-FUTURES") -> list:
        """Return all open positions for a symbol."""
        params = {"symbol": symbol, "productType": product_type}
        data = self._request("GET", "/api/v2/mix/position/allPosition", params=params)
        return data if isinstance(data, list) else []

    def place_order(
        self,
        symbol: str,
        side: str,
        size: str,
        order_type: str = "market",
        price: Optional[str] = None,
        tp_price: Optional[str] = None,
        sl_price: Optional[str] = None,
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
    ) -> dict:
        """Place a futures order. side: 'buy' or 'sell'."""
        payload: dict = {
            "symbol": symbol,
            "productType": product_type,
            "marginMode": "crossed",
            "marginCoin": margin_coin,
            "size": str(size),
            "side": side,
            "orderType": order_type,
            "tradeSide": "open",
        }
        if price:
            payload["price"] = str(price)
        if tp_price:
            payload["presetStopSurplusPrice"] = str(tp_price)
        if sl_price:
            payload["presetStopLossPrice"] = str(sl_price)

        return self._request("POST", "/api/v2/mix/order/placeOrder", data=payload)

    def close_position(
        self,
        symbol: str,
        side: str,
        size: str,
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
    ) -> dict:
        """Close an open position by placing a reverse market order."""
        close_side = "sell" if side.lower() == "buy" else "buy"
        payload = {
            "symbol": symbol,
            "productType": product_type,
            "marginMode": "crossed",
            "marginCoin": margin_coin,
            "size": str(size),
            "side": close_side,
            "orderType": "market",
            "tradeSide": "close",
        }
        return self._request("POST", "/api/v2/mix/order/placeOrder", data=payload)

    def set_leverage(
        self,
        symbol: str,
        leverage: int,
        margin_coin: str = "USDT",
        product_type: str = "USDT-FUTURES",
    ) -> dict:
        """Set leverage for a symbol."""
        payload = {
            "symbol": symbol,
            "productType": product_type,
            "marginCoin": margin_coin,
            "leverage": str(leverage),
        }
        return self._request("POST", "/api/v2/mix/account/setLeverage", data=payload)
