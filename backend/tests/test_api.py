"""The order and portfolio endpoints, called over HTTP like the browser does (with made-up live prices)."""
from datetime import datetime, timezone
from decimal import Decimal as D

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import main
import trading
from market import Quote
from seed import seed


@pytest_asyncio.fixture
async def client(session, monkeypatch, test_url):
    await seed(session)
    engine = create_async_engine(test_url)
    make_session = async_sessionmaker(engine, expire_on_commit=False)

    async def test_session():                     # endpoints use the test database instead of the real one
        async with make_session() as s:
            yield s

    async def quote(symbol):
        return Quote(bid=D("99"), ask=D("101"), time=datetime.now(timezone.utc))

    async def price(symbol):
        return D("100")

    main.app.dependency_overrides[main.get_session] = test_session
    monkeypatch.setattr(main, "live_quote", quote)              # no stream_prices.py needed
    monkeypatch.setattr(main, "last_price", price)
    monkeypatch.setattr(main, "day_open_price", price)
    monkeypatch.setattr(trading, "r", fakeredis.aioredis.FakeRedis(decode_responses=True))   # no Redis needed
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        yield c
    main.app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_buy_shows_up_in_portfolio_and_holding(client):
    res = await client.post("/orders", json={"side": "buy", "type": "market", "qty": "1"})
    assert res.status_code == 201
    order = res.json()
    assert (order["status"], order["filled_avg_price"]) == ("filled", "101")

    portfolio = (await client.get("/portfolio")).json()
    [btc] = portfolio["holdings"]
    assert (btc["symbol"], btc["qty"], btc["last_price"]) == ("BTC/USD", "1", "100")
    assert D(portfolio["cash"]) == D("100000") - D("101") - D("101") * trading.FEE
    assert portfolio["net_deposited"] == "100000"

    holding = (await client.get("/holdings/BTC")).json()
    assert holding["orders"][0]["fills"][0]["remaining"] == "1"     # the FIFO detail for the trade view


@pytest.mark.asyncio
async def test_rule_breaks_come_back_as_400_with_a_message(client):
    res = await client.post("/orders", json={"side": "sell", "type": "market", "qty": "1"})
    assert res.status_code == 400
    assert "only sell what you own" in res.json()["detail"]


@pytest.mark.asyncio
async def test_open_limit_order_can_be_cancelled(client):
    order = (await client.post("/orders", json={"side": "buy", "type": "limit", "qty": "1",
                                                "limit_price": "90"})).json()
    assert order["status"] == "open"
    assert len((await client.get("/orders?status=open")).json()) == 1
    res = await client.delete(f"/orders/{order['id']}")
    assert res.json()["status"] == "canceled"
    assert (await client.get("/orders?status=open")).json() == []
