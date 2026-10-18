"""The simulated exchange's rules, run against the test database with made-up prices."""
from datetime import datetime, timezone
from decimal import Decimal as D

import pytest
from sqlalchemy import select

import trading
from market import Quote
from models import Instrument, Order
from seed import seed

QUOTE = Quote(bid=D("99"), ask=D("101"), time=datetime.now(timezone.utc))   # spread of $2
FEE = trading.FEE                                                            # 0.25% unless FEE_RATE says otherwise


async def btc(session):
    await seed(session)                                   # user 1 with $100,000, and BTC/USD
    return await session.scalar(select(Instrument).where(Instrument.symbol == "BTC/USD"))


async def buy(session, instrument, quote=QUOTE, **kwargs):
    kwargs.setdefault("type", "market")
    return await trading.place_order(session, user_id=1, instrument=instrument, side="buy", quote=quote, **kwargs)


async def sell(session, instrument, quote=QUOTE, **kwargs):
    kwargs.setdefault("type", "market")
    return await trading.place_order(session, user_id=1, instrument=instrument, side="sell", quote=quote, **kwargs)


@pytest.mark.asyncio
async def test_market_buy_fills_at_the_ask_and_pays_the_fee(session):
    order = await buy(session, await btc(session), qty=D("2"))
    assert order.status == "filled"
    [fill] = order.fills
    assert fill.price == D("101")                         # buys pay the ask
    assert fill.fee == D("202") * FEE                     # 2 × 101 × fee rate
    assert fill.liquidity == "taker"
    account = await trading.load_account(session, 1)
    assert account.cash == D("100000") - D("202") - fill.fee


@pytest.mark.asyncio
async def test_market_sell_fills_at_the_bid(session):
    instrument = await btc(session)
    await buy(session, instrument, qty=D("2"))
    order = await sell(session, instrument, qty=D("1"))
    assert order.fills[0].price == D("99")                # sells get the bid


@pytest.mark.asyncio
async def test_dollar_amount_buy_never_costs_more_than_the_amount(session):
    order = await buy(session, await btc(session), notional=D("500"))
    fill = order.fills[0]
    assert fill.qty * fill.price + fill.fee <= D("500")
    assert fill.qty * fill.price + fill.fee > D("499.99")


@pytest.mark.asyncio
async def test_cannot_spend_more_cash_than_you_have(session):
    with pytest.raises(trading.OrderError, match="Not enough cash"):
        await buy(session, await btc(session), qty=D("1000"))   # ~$101,000 at the ask


@pytest.mark.asyncio
async def test_cannot_sell_what_you_dont_own(session):
    instrument = await btc(session)
    await buy(session, instrument, qty=D("1"))
    with pytest.raises(trading.OrderError, match="only sell what you own"):
        await sell(session, instrument, qty=D("1.5"))     # no short selling


@pytest.mark.asyncio
async def test_tiny_orders_are_refused(session):
    with pytest.raises(trading.OrderError, match="smallest order"):
        await buy(session, await btc(session), qty=D("0.001"))   # $0.10


@pytest.mark.asyncio
async def test_limit_buy_waits_reserves_cash_then_fills_at_its_price(session):
    instrument = await btc(session)
    order = await buy(session, instrument, type="limit", qty=D("100"), limit_price=D("95"))
    assert order.status == "open"                         # the ask (101) is above 95: nothing to buy yet

    account = await trading.load_account(session, 1)
    assert account.reserved_cash == D("9500") * (1 + FEE) # set aside, so it can't be spent twice
    assert account.available_cash == D("100000") - account.reserved_cash

    still_high = Quote(bid=D("96"), ask=D("97"), time=datetime.now(timezone.utc))
    assert await trading.match_open_orders(session, instrument.id, still_high) == []

    dropped = Quote(bid=D("93"), ask=D("94"), time=datetime.now(timezone.utc))
    [filled] = await trading.match_open_orders(session, instrument.id, dropped)
    assert filled.id == order.id
    await session.refresh(filled, ["fills"])
    assert filled.status == "filled"
    assert filled.fills[0].price == D("95")               # a resting limit order fills at its own price
    assert filled.fills[0].liquidity == "maker"
    assert (await trading.load_account(session, 1)).reserved_cash == 0


@pytest.mark.asyncio
async def test_limit_order_that_can_trade_now_fills_at_once(session):
    order = await buy(session, await btc(session), type="limit", qty=D("1"), limit_price=D("105"))
    assert order.status == "filled"
    assert order.fills[0].price == D("101")               # the best price on offer, not the limit


@pytest.mark.asyncio
async def test_open_sell_order_holds_the_bitcoin(session):
    instrument = await btc(session)
    await buy(session, instrument, qty=D("1"))
    await sell(session, instrument, type="limit", qty=D("1"), limit_price=D("200"))
    with pytest.raises(trading.OrderError, match="only sell what you own"):
        await sell(session, instrument, qty=D("0.5"))     # already promised to the open order


@pytest.mark.asyncio
async def test_cancel_frees_the_cash_and_cannot_be_repeated(session):
    instrument = await btc(session)
    order = await buy(session, instrument, type="limit", qty=D("10"), limit_price=D("50"))
    canceled = await trading.cancel_order(session, 1, order.id)
    assert canceled.status == "canceled"
    assert (await trading.load_account(session, 1)).reserved_cash == 0
    with pytest.raises(trading.OrderError, match="already canceled"):
        await trading.cancel_order(session, 1, order.id)
    assert await session.scalar(select(Order.status).where(Order.id == order.id)) == "canceled"
