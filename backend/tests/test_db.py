"""Database tests: tables, migrations, the seed and the constraints. Setup lives in conftest.py."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

from models import Base, CashMovement, EquitySnapshot, Fill, Instrument, Order, User
from seed import seed


@pytest.mark.asyncio
async def test_migrations_create_every_table(session):
    names = await session.run_sync(lambda s: inspect(s.connection()).get_table_names())
    assert set(Base.metadata.tables) <= set(names)                           # every model has a real table


@pytest.mark.asyncio
async def test_models_match_migrations(session):
    """Fails if models.py was changed without running `alembic revision --autogenerate`."""
    def differences(sync_session):
        context = MigrationContext.configure(sync_session.connection())
        return compare_metadata(context, Base.metadata)
    assert await session.run_sync(differences) == []


@pytest.mark.asyncio
async def test_seed_adds_starting_rows_once(session):
    await seed(session)
    await seed(session)                                                      # a second run must not duplicate anything
    assert await session.scalar(select(func.count()).select_from(User)) == 1
    assert await session.scalar(select(func.count()).select_from(Instrument)) == 1
    deposit = await session.scalar(select(CashMovement))
    assert (deposit.kind, deposit.amount) == ("deposit", Decimal("100000.00"))


@pytest.mark.asyncio
async def test_order_with_fills_round_trip(session):
    await seed(session)
    btc = await session.scalar(select(Instrument).where(Instrument.symbol == "BTC/USD"))
    now = datetime.now(timezone.utc)
    order = Order(
        user_id=1, instrument_id=btc.id, side="buy", type="limit", time_in_force="gtc",
        qty=Decimal("0.3"), limit_price=Decimal("67000.50"), status="filled",
        fills=[                                                              # one order, filled in two pieces
            Fill(qty=Decimal("0.1"), price=Decimal("67000.10"), fee=Decimal("16.75"), executed_at=now),
            Fill(qty=Decimal("0.2"), price=Decimal("67000.50"), fee=Decimal("33.50"), executed_at=now),
        ],
    )
    session.add(order)
    await session.commit()
    order_id = order.id
    session.expunge_all()                                                    # forget cached objects: re-read from Postgres

    fills = await session.run_sync(lambda s: s.get(Order, order_id).fills)
    assert [f.price for f in fills] == [Decimal("67000.10"), Decimal("67000.50")]
    assert [f.liquidity for f in fills] == ["taker", "taker"]                # the database default
    assert sum(f.qty for f in fills) == Decimal("0.3")                       # exact: with floats, 0.1 + 0.2 != 0.3


@pytest.mark.asyncio
async def test_one_balance_snapshot_per_day(session):
    await seed(session)
    today = datetime.now(timezone.utc).date()
    session.add_all([
        EquitySnapshot(user_id=1, day=today, equity=Decimal("100000"), cash=Decimal("100000")),
        EquitySnapshot(user_id=1, day=today, equity=Decimal("100001"), cash=Decimal("100000")),
    ])
    with pytest.raises(IntegrityError):                                      # Postgres refuses a second row for the same day
        await session.commit()
