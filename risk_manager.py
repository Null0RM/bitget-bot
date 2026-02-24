from typing import Tuple


class RiskManager:
    def __init__(self, risk_pct: float, sl_pct: float, tp_pct: float, leverage: int = 1):
        self.risk_pct = risk_pct      # % of balance to risk per trade
        self.sl_pct = sl_pct          # stop-loss distance %
        self.tp_pct = tp_pct          # take-profit distance %
        self.leverage = leverage

    def calculate_position_size(self, balance: float, price: float) -> float:
        """
        Calculate notional position size in base currency units.

        Risk-based formula:
            risk_amount = balance * (risk_pct / 100)   # e.g. $100 on $10k account
            sl_distance = price * (sl_pct / 100)       # $ move to stop-loss
            quantity    = risk_amount / sl_distance     # units where 1-tick loss = risk_amount

        Leverage is NOT multiplied here because `size * price_change` already gives
        the full P&L on the notional.  Leverage determines how much margin the exchange
        requires, not how large the position is for P&L purposes.
        """
        if price <= 0:
            return 0.0
        risk_amount = balance * (self.risk_pct / 100)
        sl_distance = price * (self.sl_pct / 100)
        quantity = risk_amount / sl_distance
        return round(quantity, 6)

    def calculate_sl_tp(
        self, entry: float, side: str
    ) -> Tuple[float, float]:
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
