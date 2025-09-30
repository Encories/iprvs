from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExpectancyInputs:
    p_hit: float
    tp_pct: float
    sl_pct: float
    fee_rate: float
    slip_pct: float = 0.0


def expectancy(inp: ExpectancyInputs) -> float:
    """Compute expected return per 1 unit notional before trade.

    ER = p * (tp - fees_tp - slip) + (1-p) * (-sl - fees_sl - slip)
    Fees are applied on both entry and exit sides (approx 2*fee_rate).
    """
    p = max(0.0, min(1.0, float(inp.p_hit)))
    tp = max(0.0, float(inp.tp_pct))
    sl = max(0.0, float(inp.sl_pct))
    fee = max(0.0, float(inp.fee_rate))
    slip = max(0.0, float(inp.slip_pct))
    round_trip_fees_tp = 2.0 * fee
    round_trip_fees_sl = 2.0 * fee
    gain = max(0.0, tp - round_trip_fees_tp - slip)
    loss = max(0.0, sl + round_trip_fees_sl + slip)
    return p * gain - (1.0 - p) * loss


