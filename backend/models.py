"""The database tables, written as Python classes. Alembic reads these to create and change the real tables."""
from datetime import date, datetime
from decimal import Decimal                       # exact decimal numbers: never use float for money

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

Money = Numeric(18, 2)                            # dollars and cents, e.g. 100000.00
Amount = Numeric(28, 10)                          # quantities and prices, e.g. 0.0015000000 BTC at 67012.5000000000


class Base(DeclarativeBase):                      # every table class inherits from this
    pass


class TimestampMixin:                             # created/updated times, filled in by Postgres itself
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):                 # just one user for now; logins can come later
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)


class Instrument(TimestampMixin, Base):           # anything you can trade: BTC/USD now, stocks later
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True)      # Alpaca's symbol, e.g. "BTC/USD" or "AAPL"
    name: Mapped[str] = mapped_column(String(255))                    # e.g. "Bitcoin"
    asset_class: Mapped[str] = mapped_column(String(16))              # "crypto" or "us_equity"
    shortable: Mapped[bool] = mapped_column(default=False)            # crypto can't be shorted on Alpaca
    marginable: Mapped[bool] = mapped_column(default=False)           # crypto can't use leverage on Alpaca


class Order(TimestampMixin, Base):                # every order you place, and what happened to it
    __tablename__ = "orders"                      # our backend fills these itself at live Alpaca prices (simulated exchange)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))

    side: Mapped[str] = mapped_column(String(8))                      # "buy" or "sell"
    type: Mapped[str] = mapped_column(String(16))                     # "market" or "limit"
    time_in_force: Mapped[str] = mapped_column(String(8), default="gtc")   # gtc = stays open until filled or canceled
    qty: Mapped[Decimal | None] = mapped_column(Amount)               # how much to trade, e.g. 0.0015 BTC...
    notional: Mapped[Decimal | None] = mapped_column(Money)           # ...or how many dollars' worth (one or the other)
    limit_price: Mapped[Decimal | None] = mapped_column(Amount)
    stop_price: Mapped[Decimal | None] = mapped_column(Amount)

    status: Mapped[str] = mapped_column(String(24), index=True)       # "open", "filled" or "canceled"
    filled_qty: Mapped[Decimal] = mapped_column(Amount, default=0)
    filled_avg_price: Mapped[Decimal | None] = mapped_column(Amount)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    instrument: Mapped[Instrument] = relationship()
    fills: Mapped[list["Fill"]] = relationship(back_populates="order", order_by="Fill.executed_at")


class Fill(TimestampMixin, Base):                 # one execution; an order can fill in several pieces
    __tablename__ = "fills"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    qty: Mapped[Decimal] = mapped_column(Amount)                      # bitcoin traded in this piece
    price: Mapped[Decimal] = mapped_column(Amount)                    # price per bitcoin for this piece
    fee: Mapped[Decimal] = mapped_column(Amount, server_default="0")  # simulated exchange fee, in dollars
    liquidity: Mapped[str] = mapped_column(String(8), server_default="taker")   # "taker" (filled at once) or "maker" (waited in the book)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    order: Mapped[Order] = relationship(back_populates="fills")


class CashMovement(TimestampMixin, Base):         # money in and out: the source of "total deposited"
    __tablename__ = "cash_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(16))                     # "deposit" or "withdrawal"
    amount: Mapped[Decimal] = mapped_column(Money)                    # always positive; kind says which way it went
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    note: Mapped[str | None] = mapped_column(String(255))


class EquitySnapshot(TimestampMixin, Base):       # your balance once a day, for daily P&L and a history chart
    __tablename__ = "equity_snapshots"
    __table_args__ = (UniqueConstraint("user_id", "day"),)           # one snapshot per user per day

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    day: Mapped[date] = mapped_column(Date)
    equity: Mapped[Decimal] = mapped_column(Money)                    # cash + holdings at that moment
    cash: Mapped[Decimal] = mapped_column(Money)
