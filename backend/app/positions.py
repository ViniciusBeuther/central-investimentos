"""Position of one asset from its transactions and corporate actions, using the weighted
average price.

Pure functions, no database: easy to test. Nothing here is stored; positions are always
computed from the transactions and corporate actions.

Rules (standard for Brazilian income tax):
- Buy:  quantity += q;  cost += value.
- Sell: the cost leaving the position is q x average price, NOT the sale value.
        The average price does not change on a sale.
        Profit/loss of the sale = sale value - cost leaving.

Corporate actions (quantities exactly as the B3 Movimentação report gives them):
- split:         quantity += extra shares credited; cost unchanged.
- reverse_split: quantity = resulting shares (may be fractional); cost unchanged.
- bonus:         quantity += shares credited; cost += shares x declared cost per share
                 (0 when unknown, which lowers the average price and is reported).
- fraction:      the leftover fraction leaves the position at average price; the auction
                 cash counts as the sale value of that fraction.

- transfer_out / transfer_in: B3 'Transferência' (e.g. KLBN11 -> KLBN3 + KLBN4). Quantity
                 leaves one ticker and enters another. The cost that travels is
                 quantity x cost_per_share of the row (unknown = 0, reported), so the
                 total cost is conserved when both sides carry the same cost per share.

An action takes effect at the START of its date, before that day's trades.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

ZERO = Decimal(0)

# (trade_date, 'buy'|'sell', quantity, total_value)
Trade = tuple[date, str, Decimal, Decimal]
# (action_date, kind, quantity, cost_per_share or None, cash_amount or None)
Action = tuple[date, str, Decimal, Decimal | None, Decimal | None]


@dataclass
class Position:
    quantity: Decimal = ZERO
    cost: Decimal = ZERO  # total cost of the shares still held
    realized_profit: Decimal = ZERO  # accumulated profit/loss of sales
    warnings: list[str] = field(default_factory=list)

    @property
    def average_price(self) -> Decimal:
        return self.cost / self.quantity if self.quantity else ZERO

    def _remove(self, quantity: Decimal, proceeds: Decimal) -> None:
        """Take shares out at average price and book the profit against the proceeds."""
        cost_out = quantity * self.average_price
        self.realized_profit += proceeds - cost_out
        self.cost -= cost_out
        self.quantity -= quantity


def compute_position(trades: list[Trade], actions: list[Action] | None = None) -> Position:
    """Same-day order: corporate actions, then buys, then sells (B3 trades carry no time)."""
    events = [(t[0], 1 if t[1] == "buy" else 2, t) for t in trades]
    events += [(a[0], 0, a) for a in actions or []]
    events.sort(key=lambda e: (e[0], e[1]))

    position = Position()
    for event_date, order, event in events:
        if order == 0:
            _apply_action(position, event)
        else:
            _apply_trade(position, event)
    return position


def _apply_trade(position: Position, trade: Trade) -> None:
    trade_date, kind, quantity, value = trade
    if kind == "buy":
        position.quantity += quantity
        position.cost += value
    elif kind == "sell":
        if quantity > position.quantity:
            position.warnings.append(f"{trade_date}: sold {quantity} but position was {position.quantity}")
            quantity = position.quantity  # never go negative
        position._remove(quantity, value)
    else:
        raise ValueError(f"unknown kind {kind!r}")


def _apply_action(position: Position, action: Action) -> None:
    action_date, kind, quantity, cost_per_share, cash = action
    if kind == "split":
        position.quantity += quantity
    elif kind == "reverse_split":
        position.quantity = quantity
    elif kind == "bonus":
        position.quantity += quantity
        if cost_per_share is None:
            position.warnings.append(f"{action_date}: bonus of {quantity} with unknown cost (counted as 0)")
        else:
            position.cost += quantity * cost_per_share
    elif kind == "fraction":
        if quantity > position.quantity:
            position.warnings.append(f"{action_date}: fraction {quantity} larger than position {position.quantity}")
            quantity = position.quantity
        position._remove(quantity, cash or ZERO)
    elif kind in ("transfer_out", "transfer_in"):
        sign = -1 if kind == "transfer_out" else 1
        if kind == "transfer_out" and quantity > position.quantity:
            position.warnings.append(f"{action_date}: transfer out {quantity} larger than position {position.quantity}")
            quantity = position.quantity
        position.quantity += sign * quantity
        if cost_per_share is None:
            position.warnings.append(f"{action_date}: {kind} of {quantity} with unknown cost (counted as 0)")
        else:
            position.cost += sign * quantity * cost_per_share
    else:
        raise ValueError(f"unknown corporate action {kind!r}")
