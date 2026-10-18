"""The simulated exchange: placing, filling and cancelling orders, with all the money checks.

Prices come from Alpaca's live feed (via Redis); the trades themselves happen only in our database.
  - A market buy fills at the ask, a market sell at the bid, like a real exchange (so you pay the spread).
  - A limit order that can trade straight away fills the same way; otherwise it waits ("open") until
    match_orders.py sees the price reach it, then fills at the limit price.
  - Every fill pays a simulated fee (FEE_RATE in config.py).
"""
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import func, or_, and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import FEE_RATE
from market import Quote
from models import CashMovement, Fill, Instrument, Order, User
from portfolio import FillRow, build_position, cash_balance
from redis_client import r

FEE = Decimal(FEE_RATE)
QTY_STEP = Decimal("0.00000001")                  # trade sizes are rounded down to 8 decimals (1 satoshi)
MIN_ORDER_VALUE = Decimal("1")                    # smallest order allowed, in dollars


class OrderError(Exception):
    """The order breaks a rule (not enough cash, bad price...). The message is shown to the user."""


@dataclass
class Account:                                    # a user's money, worked out from the database
    deposits: Decimal
    withdrawals: Decimal
    cash: Decimal                                 # all cash, including cash set aside for open buy orders
    reserved_cash: Decimal                        # set aside for open limit buys
    fills: list[FillRow]                          # every fill, for P&L

    @property
    def available_cash(self) -> Decimal:
        return self.cash - self.reserved_cash


def fill_rows(fills: list[Fill]) -> list[FillRow]:
    return [FillRow(f.id, f.order_id, f.order.side, f.qty, f.price, f.fee, f.executed_at) for f in fills]


async def load_fills(session: AsyncSession, user_id: int, instrument_id: int | None = None) -> list[Fill]:
    query = (select(Fill).join(Order).where(Order.user_id == user_id)
             .options(selectinload(Fill.order)).order_by(Fill.executed_at, Fill.id))
    if instrument_id is not None:
        query = query.where(Order.instrument_id == instrument_id)
    return list(await session.scalars(query))


async def load_account(session: AsyncSession, user_id: int) -> Account:
    async def total(kind: str) -> Decimal:
        value = await session.scalar(select(func.coalesce(func.sum(CashMovement.amount), 0))
                                     .where(CashMovement.user_id == user_id, CashMovement.kind == kind))
        return Decimal(value)

    deposits, withdrawals = await total("deposit"), await total("withdrawal")
    fills = fill_rows(await load_fills(session, user_id))
    open_buys = await session.scalars(select(Order).where(
        Order.user_id == user_id, Order.status == "open", Order.side == "buy"))
    reserved = sum((reserve_for(o) for o in open_buys), Decimal("0"))
    return Account(deposits, withdrawals, cash_balance(deposits, withdrawals, fills), reserved, fills)


def reserve_for(order: Order) -> Decimal:
    """Cash an open buy order needs set aside: its full cost at the limit price, plus the fee."""
    return order.qty * order.limit_price * (1 + FEE)


async def held_qty(session: AsyncSession, user_id: int, instrument_id: int) -> tuple[Decimal, Decimal]:
    """(amount held, amount already promised to open sell orders) for one instrument."""
    position = build_position(fill_rows(await load_fills(session, user_id, instrument_id)))
    promised = await session.scalar(select(func.coalesce(func.sum(Order.qty), 0)).where(
        Order.user_id == user_id, Order.instrument_id == instrument_id,
        Order.status == "open", Order.side == "sell"))
    return position.qty, Decimal(promised)


async def place_order(
    session: AsyncSession, *, user_id: int, instrument: Instrument, side: str, type: str,
    quote: Quote, qty: Decimal | None = None, notional: Decimal | None = None,
    limit_price: Decimal | None = None, now: datetime | None = None,
) -> Order:
    """Check the order against the rules, save it, and fill it straight away if it can trade now."""
    now = now or datetime.now(timezone.utc)
    if side not in ("buy", "sell"):
        raise OrderError("Side must be buy or sell.")
    if type not in ("market", "limit"):
        raise OrderError("Order type must be market or limit.")
    if (qty is None) == (notional is None):
        raise OrderError("Give either a quantity or a dollar amount, not both.")
    if type == "limit" and (limit_price is None or limit_price <= 0):
        raise OrderError("A limit order needs a limit price above zero.")
    if type == "market":
        limit_price = None

    # lock this user's row until we commit, so two orders at once can't both spend the same cash
    await session.execute(select(User).where(User.id == user_id).with_for_update())

    price = limit_price if type == "limit" else (quote.ask if side == "buy" else quote.bid)
    if notional is not None:                      # "$100 of bitcoin": work out the bitcoin amount
        if notional <= 0:
            raise OrderError("The amount must be above zero.")
        qty = notional / (price * (1 + FEE)) if side == "buy" else notional / price   # buys: leave room for the fee
    qty = qty.quantize(QTY_STEP, rounding=ROUND_DOWN)
    if qty <= 0:
        raise OrderError("The amount is too small.")
    if qty * price < MIN_ORDER_VALUE:
        raise OrderError(f"The smallest order is ${MIN_ORDER_VALUE}.")

    if side == "buy":
        cost = qty * price * (1 + FEE)
        available = (await load_account(session, user_id)).available_cash
        if cost > available:
            raise OrderError(f"Not enough cash: this needs ${cost:,.2f} but you have ${available:,.2f} available.")
    else:
        if instrument.asset_class == "crypto" or not instrument.shortable:
            held, promised = await held_qty(session, user_id, instrument.id)
            if qty > held - promised:             # no short selling: you can only sell what you own
                raise OrderError(f"You can only sell what you own: {held - promised:f} {instrument.symbol.split('/')[0]} available.")

    order = Order(
        user_id=user_id, instrument_id=instrument.id, side=side, type=type, time_in_force="gtc",
        qty=qty, notional=notional, limit_price=limit_price, status="open", submitted_at=now,
    )
    session.add(order)
    await session.flush()                         # get the order its id

    can_trade_now = (type == "market"
                     or (side == "buy" and quote.ask <= limit_price)
                     or (side == "sell" and quote.bid >= limit_price))
    if can_trade_now:                             # takes the best price on offer right now
        fill_order(session, order, quote.ask if side == "buy" else quote.bid, "taker", now)

    await session.commit()
    await session.refresh(order, ["fills", "instrument"])
    return order


def fill_order(session: AsyncSession, order: Order, price: Decimal, liquidity: str, now: datetime) -> Fill:
    """Fill the whole order at this price. The caller commits."""
    fee = (order.qty * price * FEE).quantize(QTY_STEP)
    fill = Fill(order_id=order.id, qty=order.qty, price=price, fee=fee, liquidity=liquidity, executed_at=now)
    session.add(fill)
    order.status = "filled"
    order.filled_qty = order.qty
    order.filled_avg_price = price
    order.filled_at = now
    return fill


async def cancel_order(session: AsyncSession, user_id: int, order_id: int) -> Order:
    order = await session.scalar(select(Order).where(Order.id == order_id, Order.user_id == user_id)
                                 .with_for_update())      # lock it, so the matcher can't fill it mid-cancel
    if order is None:
        raise OrderError("Order not found.")
    if order.status != "open":
        raise OrderError(f"This order is already {order.status}.")
    order.status = "canceled"
    order.canceled_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(order, ["fills", "instrument"])
    return order


async def match_open_orders(session: AsyncSession, instrument_id: int, quote: Quote,
                            now: datetime | None = None) -> list[Order]:
    """Fill every open limit order the market has reached. Used by match_orders.py on each new quote.

    A resting buy limit fills when sellers come down to it (ask <= limit), a sell limit when buyers
    come up to it (bid >= limit). Both fill at their own limit price, as "maker" fills.
    """
    now = now or datetime.now(timezone.utc)
    reached = await session.scalars(
        select(Order)
        .where(Order.instrument_id == instrument_id, Order.status == "open", Order.type == "limit",
               or_(and_(Order.side == "buy", Order.limit_price >= quote.ask),
                   and_(Order.side == "sell", Order.limit_price <= quote.bid)))
        .with_for_update(skip_locked=True)        # skip any order the API is cancelling right now
    )
    filled = []
    for order in reached:
        fill_order(session, order, order.limit_price, "maker", now)
        filled.append(order)
    await session.commit()
    return filled


async def announce(order: Order, event: str):
    """Tell any open browser about the order straight away (main.py relays the "orders:<user>" channel)."""
    await r.publish(f"orders:{order.user_id}", json.dumps({"event": event, "order_id": order.id,
                                                           "status": order.status}))
