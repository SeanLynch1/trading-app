"""Live market prices, read from Redis (where stream_prices.py writes them) and from Alpaca's candle history."""
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from config import ALPACA_API_KEY, ALPACA_SECRET_KEY
from redis_client import r

MAX_QUOTE_AGE = timedelta(seconds=60)             # refuse to trade on a price older than this

bars_client = CryptoHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)


class NoPriceError(Exception):
    """There's no recent live price, so we can't safely fill an order."""


@dataclass
class Quote:
    bid: Decimal                                  # best price a buyer is offering: what a sell fills at
    ask: Decimal                                  # best price a seller is asking: what a buy fills at
    time: datetime


def parse_time(iso: str) -> datetime:
    """Alpaca's "2026-10-18T17:30:12.123456789Z" -> a datetime (Python only keeps 6 decimals of seconds)."""
    head, _, rest = iso.rstrip("Z").partition(".")
    return datetime.fromisoformat(f"{head}.{(rest or '0')[:6]}").replace(tzinfo=timezone.utc)


def to_quote(data: dict) -> Quote:
    return Quote(bid=Decimal(str(data["bid"])), ask=Decimal(str(data["ask"])), time=parse_time(data["time"]))


async def live_quote(symbol: str) -> Quote:
    """The latest bid/ask for e.g. "BTC/USD", or NoPriceError if there isn't a fresh one."""
    data = await r.hgetall(f"quote:{symbol}")
    if not data:
        raise NoPriceError(f"No live price for {symbol}. Is stream_prices.py running?")
    quote = to_quote(data)
    if datetime.now(timezone.utc) - quote.time > MAX_QUOTE_AGE:
        raise NoPriceError(f"The live price for {symbol} is out of date. Is stream_prices.py running?")
    return quote


async def last_price(symbol: str) -> Decimal | None:
    """The price of the most recent trade, used to value holdings. None if there isn't one yet."""
    price = await r.hget(f"last_trade:{symbol}", "price")
    if price is None:                             # no trade yet: fall back to the middle of the bid/ask
        data = await r.hgetall(f"quote:{symbol}")
        return (Decimal(data["bid"]) + Decimal(data["ask"])) / 2 if data else None
    return Decimal(price)


def day_start(now: datetime | None = None) -> datetime:
    """Midnight UTC today: crypto trades around the clock, so "today" starts at 00:00 UTC."""
    now = now or datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def day_open_price(symbol: str) -> Decimal | None:
    """The price at 00:00 UTC today, for daily P&L. Asked from Alpaca once a day, then kept in Redis."""
    start = day_start()
    key = f"day_open:{symbol}:{start.date()}"
    cached = await r.get(key)
    if cached:
        return Decimal(cached)

    def fetch():                                  # Alpaca's client blocks, so run it in a thread (see asyncio.to_thread)
        request = CryptoBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame(1, TimeFrameUnit.Minute),
            start=start, end=start + timedelta(minutes=30),   # the first candle after midnight
        )
        bars = bars_client.get_crypto_bars(request).data.get(symbol, [])
        return Decimal(str(bars[0].open)) if bars else None

    try:
        price = await asyncio.to_thread(fetch)
    except Exception:                             # Alpaca unreachable: daily P&L just shows as unknown for now
        return None
    if price is not None:
        await r.set(key, str(price), ex=26 * 60 * 60)   # keep it a little over a day
    return price
