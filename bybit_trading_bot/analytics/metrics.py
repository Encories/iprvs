from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FillMetrics:
    total_orders: int = 0
    filled_orders: int = 0
    total_slippage_bp: float = 0.0

    def on_fill(self, slippage_bp: float) -> None:
        self.total_orders += 1
        self.filled_orders += 1
        self.total_slippage_bp += float(slippage_bp)

    def on_place(self) -> None:
        self.total_orders += 1

    @property
    def fill_rate(self) -> float:
        return (self.filled_orders / self.total_orders) if self.total_orders > 0 else 0.0

    @property
    def avg_slippage_bp(self) -> float:
        return (self.total_slippage_bp / max(1, self.filled_orders)) if self.filled_orders > 0 else 0.0


