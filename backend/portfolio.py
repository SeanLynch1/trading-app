"""Portfolio maths: cash, holdings and profit/loss, calculated from fills.

Everything here is plain Python on plain data (no database, no network), so it's easy to test.
Sells are matched to earlier buys first-in-first-out (FIFO): selling 0.1 BTC uses up the oldest
bitcoin you still hold, which is how per-trade profit is worked out.
"""
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

ZERO = Decimal("0")


@dataclass
class FillRow:                                    # one fill, with its order's side attached
    id: int
    order_id: int
    side: str                                     # "buy" or "sell"
    qty: Decimal
    price: Decimal
    fee: Decimal
    executed_at: datetime


@dataclass
class FillResult:                                 # what FIFO matching worked out for one fill
    kind: str                                     # "buy" or "sell"
    qty: Decimal
    price: Decimal
    fee: Decimal
    cash_flow: Decimal                            # buy: dollars spent incl. fee; sell: dollars received after fee
    remaining: Decimal = ZERO                     # buy: bitcoin from this buy you still hold
    cost_left: Decimal = ZERO                     # buy: what that remaining bitcoin cost you (incl. its share of the fee)
    realized: Decimal = ZERO                      # profit already locked in: for a buy, from the part since sold;
                                                  # for a sell, the whole sale's profit vs. what that bitcoin cost


@dataclass
class Position:                                   # one instrument, all fills applied
    qty: Decimal = ZERO                           # bitcoin held now
    cost_basis: Decimal = ZERO                    # what the bitcoin held now cost, fees included
    realized: Decimal = ZERO                      # profit locked in by sells, after fees
    fees: Decimal = ZERO                          # all fees paid on this instrument
    fills: dict[int, FillResult] = field(default_factory=dict)   # per fill id

    @property
    def avg_price(self) -> Decimal | None:        # average cost per bitcoin held, fees included
        return self.cost_basis / self.qty if self.qty else None

    def unrealized(self, price: Decimal) -> Decimal:   # paper profit on what you still hold, at this price
        return self.qty * price - self.cost_basis

    def total_pnl(self, price: Decimal) -> Decimal:    # all-time profit: locked in + on paper
        return self.realized + self.unrealized(price)


def build_position(fills: list[FillRow]) -> Position:
    """Replay fills oldest-first, matching each sell to the oldest bitcoin still held."""
    pos = Position()
    lots: deque[list] = deque()                   # [fill id, bitcoin left, cost per bitcoin] for each buy still held

    for f in sorted(fills, key=lambda f: (f.executed_at, f.id)):
        pos.fees += f.fee
        if f.side == "buy":
            cost = f.qty * f.price + f.fee        # the fee is part of what the bitcoin cost you
            pos.fills[f.id] = FillResult("buy", f.qty, f.price, f.fee, cash_flow=cost, remaining=f.qty, cost_left=cost)
            lots.append([f.id, f.qty, cost / f.qty])
            continue

        proceeds = f.qty * f.price - f.fee        # what the sale actually paid you
        per_btc = proceeds / f.qty
        result = FillResult("sell", f.qty, f.price, f.fee, cash_flow=proceeds)
        to_match = f.qty
        while to_match > 0 and lots:              # use up the oldest buys first
            lot = lots[0]
            take = min(to_match, lot[1])
            cost = take * lot[2]
            bought = pos.fills[lot[0]]
            bought.remaining -= take
            bought.cost_left -= cost
            bought.realized += take * per_btc - cost
            result.realized += take * per_btc - cost
            lot[1] -= take
            to_match -= take
            if lot[1] == 0:
                lots.popleft()
        pos.fills[f.id] = result
        pos.realized += result.realized

    pos.qty = sum((lot[1] for lot in lots), ZERO)
    pos.cost_basis = sum((lot[1] * lot[2] for lot in lots), ZERO)
    return pos


def cash_balance(deposits: Decimal, withdrawals: Decimal, fills: list[FillRow]) -> Decimal:
    """Money in, minus money spent on buys, plus money from sells (fees included both ways)."""
    cash = deposits - withdrawals
    for f in fills:
        if f.side == "buy":
            cash -= f.qty * f.price + f.fee
        else:
            cash += f.qty * f.price - f.fee
    return cash


def day_figures(fills: list[FillRow], day_start: datetime) -> tuple[Decimal, Decimal, Decimal]:
    """What's needed for today's P&L: (bitcoin held when the day started, net dollars put in since,
    dollars spent on buys today).

    Today's P&L = value now − value at the start of the day − money added today
                = qty_now × price_now − qty_start × price_start − net_flow
    Today's %   = that P&L ÷ (value at the start of the day + money spent on buys today)
    """
    qty_start = ZERO
    net_flow = ZERO                               # dollars spent on buys today minus dollars received from sells today
    bought = ZERO                                 # dollars spent on buys today
    for f in fills:
        signed = f.qty if f.side == "buy" else -f.qty
        if f.executed_at < day_start:
            qty_start += signed
        elif f.side == "buy":
            net_flow += f.qty * f.price + f.fee
            bought += f.qty * f.price + f.fee
        else:
            net_flow -= f.qty * f.price - f.fee
    return qty_start, net_flow, bought


def daily_pnl(qty_now: Decimal, price_now: Decimal, qty_start: Decimal,
              price_start: Decimal, net_flow: Decimal) -> Decimal:
    return qty_now * price_now - qty_start * price_start - net_flow
