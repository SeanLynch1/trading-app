"""Fills a fresh database with the starting rows. Safe to run more than once: it only adds what's missing.

Run it after `alembic upgrade head`:   python seed.py
"""
import asyncio
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import STARTING_CASH
from models import CashMovement, Instrument, User


async def seed(session: AsyncSession):
    """Add the starting rows using the given session (the app's database, or a test database)."""
    user = await session.scalar(select(User).order_by(User.id).limit(1))
    if user is None:                              # the single user, until the app has logins
        user = User()
        session.add(user)
        await session.flush()                     # send it to Postgres now, so it gets its id (1 on a fresh database)

    btc = await session.scalar(select(Instrument).where(Instrument.symbol == "BTC/USD"))
    if btc is None:
        session.add(Instrument(
            symbol="BTC/USD", name="Bitcoin", asset_class="crypto",
            shortable=False, marginable=False,    # Alpaca: crypto is long-only, no leverage
        ))

    deposited = await session.scalar(select(CashMovement).where(CashMovement.user_id == user.id).limit(1))
    if deposited is None:                         # a paper account starts with fake money; record it as the first deposit
        session.add(CashMovement(
            user_id=user.id, kind="deposit", amount=Decimal(STARTING_CASH),
            note="Paper account starting balance",
        ))

    await session.commit()                        # save it all, or nothing if anything above failed


async def main():
    from db import Session, engine                # the real database from config.py (imported here, not at the top,
                                                  # so tests can import seed() without connecting to it)
    async with Session() as session:
        await seed(session)
    await engine.dispose()                        # close the connection pool so the script can exit cleanly
    print("Database seeded.")


if __name__ == "__main__":
    asyncio.run(main())
