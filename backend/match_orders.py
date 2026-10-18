"""Fills open limit orders when the live price reaches them, and saves a daily balance snapshot.

Run it next to stream_prices.py:   python match_orders.py

It listens to the bid/ask updates stream_prices.py publishes to Redis. For each new price it asks the
database for open limit orders that price has reached, fills them, and tells the browser.
"""
import asyncio
import json
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

import trading
from db import Session
from market import last_price, to_quote
from models import EquitySnapshot, Instrument, User
from portfolio import build_position
from redis_client import r

CHECK_EVERY = 0.25                                # seconds: at most 4 checks a second per instrument, using the newest price
SNAPSHOT_EVERY = 5 * 60                           # seconds between balance snapshots


async def match_forever():
    async with Session() as session:              # symbol -> instrument id, e.g. "BTC/USD" -> 1
        ids = {i.symbol: i.id for i in await session.scalars(select(Instrument))}

    pubsub = r.pubsub()
    await pubsub.psubscribe("quotes:*")           # every instrument's bid/ask channel ("quotes:BTC/USD", ...)
    last_check: dict[str, float] = {}
    print("Matching limit orders against live prices...", flush=True)

    async for message in pubsub.listen():         # sleeps until a new quote arrives
        if message["type"] != "pmessage":
            continue
        symbol = message["channel"].split(":", 1)[1]
        if symbol not in ids or time.monotonic() - last_check.get(symbol, 0) < CHECK_EVERY:
            continue                              # unknown instrument, or checked a moment ago
        last_check[symbol] = time.monotonic()

        quote = to_quote(json.loads(message["data"]))
        async with Session() as session:
            filled = await trading.match_open_orders(session, ids[symbol], quote)
        for order in filled:
            await trading.announce(order, "filled")
            print(f"Filled order {order.id}: {order.side} {order.qty} {symbol} at {order.limit_price}", flush=True)


async def snapshot_forever():
    """Every few minutes, save each user's balance (cash + holdings at the last price) as today's snapshot."""
    while True:
        try:
            await save_snapshots()
        except Exception as e:                    # e.g. no price yet: try again next time
            print(f"snapshot skipped: {e}", flush=True)
        await asyncio.sleep(SNAPSHOT_EVERY)


async def save_snapshots():
    async with Session() as session:
        instruments = list(await session.scalars(select(Instrument)))
        prices = {i.id: await last_price(i.symbol) for i in instruments}
        for user in await session.scalars(select(User)):
            account = await trading.load_account(session, user.id)
            equity = account.cash
            for i in instruments:
                qty = build_position(trading.fill_rows(await trading.load_fills(session, user.id, i.id))).qty
                if qty and prices[i.id] is None:
                    raise RuntimeError(f"no price for {i.symbol} yet")
                if qty:
                    equity += qty * prices[i.id]
            today = datetime.now(timezone.utc).date()
            await session.execute(                # one row per user per day: insert, or update today's row
                insert(EquitySnapshot)
                .values(user_id=user.id, day=today, equity=equity, cash=account.cash)
                .on_conflict_do_update(index_elements=["user_id", "day"],
                                       set_={"equity": equity, "cash": account.cash}))
        await session.commit()


async def main():
    await asyncio.gather(match_forever(), snapshot_forever())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Matcher stopped.")
