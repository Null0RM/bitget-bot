from typing import Tuple


class RiskManager:
    def __init__(self, collateral_pct: float, sl_pct: float, tp_pct: float, leverage: int = 1):
        self.collateral_pct = collateral_pct  # % of balance to use as collateral per trade
        self.sl_pct  = sl_pct                 # stop-loss distance %
        self.tp_pct  = tp_pct                 # take-profit distance %
        self.leverage = leverage

    def calculate_position_size(self, balance: float, price: float) -> float:
        """
        Collateral-based position sizing.

            collateral = balance * (collateral_pct / 100)   e.g. 10% of $50 = $5
            notional   = collateral * leverage              e.g. $5 * 8 = $40
            quantity   = notional / price                   e.g. $40 / $95000 = 0.000421 BTC
        """
        if price <= 0:
            return 0.0
        collateral = balance * (self.collateral_pct / 100)
        notional   = collateral * self.leverage
        quantity   = notional / price
        return round(quantity, 6)

    def calculate_sl_tp(self, entry: float, side: str) -> Tuple[float, float]:
        """
        Return (sl_price, tp_price) for a given entry and side.

        Long  (buy):  sl = entry - entry*sl_pct/100,  tp = entry + entry*tp_pct/100
        Short (sell): sl = entry + entry*sl_pct/100,  tp = entry - entry*tp_pct/100
        """
        sl_distance = entry * (self.sl_pct / 100)
        tp_distance = entry * (self.tp_pct / 100)

        if side.lower() == "buy":
            sl_price = round(entry - sl_distance, 4)
            tp_price = round(entry + tp_distance, 4)
        else:
            sl_price = round(entry + sl_distance, 4)
            tp_price = round(entry - tp_distance, 4)

        return sl_price, tp_price
