from datetime import datetime, timedelta, timezone   # to work out how far back the candle history starts
from decimal import Decimal
from typing import Literal

from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware   # lets the React app (another port) call this API
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import trading
from db import Session
from market import NoPriceError, bars_client, day_open_price, day_start, last_price, live_quote
from models import Instrument, Order
from portfolio import Position, build_position, day_figures
from redis_client import r                        # same shared async Redis connection the stream uses

app = FastAPI()                                   # the web app; uvicorn runs this object

app.add_middleware(                               # CORS: which websites may call this API from a browser
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],      # the Vite dev server running the React app
    allow_methods=["GET", "POST", "DELETE"],      # POST places orders, DELETE cancels them
    allow_headers=["*"],
)


# ---------- shared helpers ----------

async def get_session():                          # one database session per request, closed afterwards
    async with Session() as session:
        yield session


def current_user() -> int:                        # always user 1 until the app has logins; then this checks the login
    return 1


async def find_instrument(session: AsyncSession, symbol: str) -> Instrument:
    """Accepts "BTC", "btc", "BTC-USD" or "BTC/USD"."""
    symbol = symbol.upper().replace("-", "/")
    instrument = await session.scalar(select(Instrument).where(Instrument.symbol.in_([symbol, f"{symbol}/USD"])))
    if instrument is None:
        raise HTTPException(status_code=404, detail=f"Unknown symbol {symbol}")
    return instrument


def num(value: Decimal | None) -> str | None:     # money goes out as strings, so no precision is lost in JSON
    return None if value is None else f"{value.normalize():f}"


def order_json(order: Order, position: Position | None = None) -> dict:
    """An order with its fills. With a position, each fill also gets its FIFO cost and profit."""
    fills = []
    for f in sorted(order.fills, key=lambda f: f.executed_at):
        item = {"id": f.id, "qty": num(f.qty), "price": num(f.price), "fee": num(f.fee),
                "liquidity": f.liquidity, "executed_at": f.executed_at.isoformat()}
        if position and f.id in position.fills:
            result = position.fills[f.id]
            item.update(cash_flow=num(result.cash_flow), remaining=num(result.remaining),
                        cost_left=num(result.cost_left), realized=num(result.realized))
        fills.append(item)
    return {
        "id": order.id, "symbol": order.instrument.symbol, "name": order.instrument.name,
        "side": order.side, "type": order.type, "status": order.status,
        "qty": num(order.qty), "notional": num(order.notional), "limit_price": num(order.limit_price),
        "filled_avg_price": num(order.filled_avg_price),
        "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
        "filled_at": order.filled_at.isoformat() if order.filled_at else None,
        "canceled_at": order.canceled_at.isoformat() if order.canceled_at else None,
        "fills": fills,
    }


async def holding_json(session: AsyncSession, user_id: int, instrument: Instrument) -> dict:
    """One holding: the parts the browser needs to work out live value and P&L from the live price.

    value     = qty × price
    total P&L = realized + value − cost_basis
    today P&L = qty × price − qty_day_start × day_open_price − day_net_flow
    today %   = today P&L ÷ (qty_day_start × day_open_price + day_bought)
    """
    fills = trading.fill_rows(await trading.load_fills(session, user_id, instrument.id))
    position = build_position(fills)
    qty_day_start, day_net_flow, day_bought = day_figures(fills, day_start())
    open_orders = await session.scalar(select(func.count()).select_from(Order).where(
        Order.user_id == user_id, Order.instrument_id == instrument.id, Order.status == "open"))
    _, qty_reserved = await trading.held_qty(session, user_id, instrument.id)   # promised to open sell orders
    return {
        "symbol": instrument.symbol, "name": instrument.name, "asset_class": instrument.asset_class,
        "shortable": instrument.shortable, "marginable": instrument.marginable,
        "qty": num(position.qty), "qty_reserved": num(qty_reserved), "cost_basis": num(position.cost_basis),
        "avg_price": num(position.avg_price), "realized": num(position.realized), "fees": num(position.fees),
        "last_price": num(await last_price(instrument.symbol)),
        "day_open_price": num(await day_open_price(instrument.symbol)),
        "qty_day_start": num(qty_day_start), "day_net_flow": num(day_net_flow), "day_bought": num(day_bought),
        "open_orders": open_orders, "has_history": bool(fills) or open_orders > 0,
    }


# ---------- market data ----------

@app.get("/quote/{symbol}")                       # GET /quote/BTC -> latest bid/ask, once (pull)
async def get_quote(symbol: str):
    quote = await r.hgetall(f"quote:{symbol.upper()}/USD")   # read the latest bid/ask the stream saved
    if not quote:                                 # nothing stored for that symbol (or stream not running)
        raise HTTPException(status_code=404, detail=f"No quote for {symbol.upper()}")
    return quote                                  # FastAPI turns the dictionary into JSON


TIMEFRAMES = {                                    # the chart's buttons -> (Alpaca timeframe, seconds per candle)
    "1m":  (TimeFrame(1, TimeFrameUnit.Minute), 60),
    "5m":  (TimeFrame(5, TimeFrameUnit.Minute), 5 * 60),
    "10m": (TimeFrame(10, TimeFrameUnit.Minute), 10 * 60),
    "30m": (TimeFrame(30, TimeFrameUnit.Minute), 30 * 60),
    "1h":  (TimeFrame(1, TimeFrameUnit.Hour), 60 * 60),
    "4h":  (TimeFrame(4, TimeFrameUnit.Hour), 4 * 60 * 60),
    "1d":  (TimeFrame(1, TimeFrameUnit.Day), 24 * 60 * 60),
    "1w":  (TimeFrame(1, TimeFrameUnit.Week), 7 * 24 * 60 * 60),
}
CANDLES = 300                                     # how many candles of history to send, whatever the timeframe


@app.get("/bars/{symbol}")                        # GET /bars/BTC?timeframe=5m -> the last 300 five-minute candles
def get_bars(symbol: str, timeframe: str = "1m"): # plain def: Alpaca's client blocks, so FastAPI runs this in a thread
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"timeframe must be one of {', '.join(TIMEFRAMES)}")
    alpaca_timeframe, seconds = TIMEFRAMES[timeframe]
    pair = f"{symbol.upper()}/USD"
    request = CryptoBarsRequest(
        symbol_or_symbols=pair,
        timeframe=alpaca_timeframe,
        start=datetime.now(timezone.utc) - timedelta(seconds=seconds * CANDLES),   # far enough back for 300 candles
    )
    bars = bars_client.get_crypto_bars(request)   # ask Alpaca for the candles over the internet
    return [                                      # the shape lightweight-charts expects
        {
            "time": int(b.timestamp.timestamp()), # Unix time in seconds, the start of the candle
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,                   # bitcoin traded during the candle, for the volume bars
        }
        for b in bars.data.get(pair, [])          # periods with no trades simply have no candle
    ]


# ---------- portfolio ----------

@app.get("/portfolio")                            # everything the Portfolio page needs
async def get_portfolio(session: AsyncSession = Depends(get_session), user_id: int = Depends(current_user)):
    account = await trading.load_account(session, user_id)
    instruments = await session.scalars(select(Instrument).order_by(Instrument.symbol))
    holdings = [await holding_json(session, user_id, i) for i in instruments]
    return {
        "deposits": num(account.deposits), "withdrawals": num(account.withdrawals),
        "net_deposited": num(account.deposits - account.withdrawals),
        "cash": num(account.cash), "reserved_cash": num(account.reserved_cash),
        "available_cash": num(account.available_cash), "fee_rate": num(trading.FEE),
        "holdings": [h for h in holdings if h["has_history"]],   # only things you've traded
    }


@app.get("/holdings/{symbol}")                    # GET /holdings/BTC -> the position plus every order for it
async def get_holding(symbol: str, session: AsyncSession = Depends(get_session),
                      user_id: int = Depends(current_user)):
    instrument = await find_instrument(session, symbol)
    position = build_position(trading.fill_rows(await trading.load_fills(session, user_id, instrument.id)))
    orders = await session.scalars(
        select(Order).where(Order.user_id == user_id, Order.instrument_id == instrument.id)
        .options(selectinload(Order.fills), selectinload(Order.instrument))
        .order_by(Order.submitted_at.desc(), Order.id.desc()))
    return {"holding": await holding_json(session, user_id, instrument),
            "orders": [order_json(o, position) for o in orders]}


# ---------- orders ----------

class OrderIn(BaseModel):                         # what the order ticket sends
    symbol: str = "BTC/USD"
    side: Literal["buy", "sell"]
    type: Literal["market", "limit"]
    qty: Decimal | None = None                    # an amount of bitcoin...
    notional: Decimal | None = None               # ...or a dollar amount (one or the other)
    limit_price: Decimal | None = None            # limit orders only


@app.post("/orders", status_code=201)
async def create_order(body: OrderIn, session: AsyncSession = Depends(get_session),
                       user_id: int = Depends(current_user)):
    instrument = await find_instrument(session, body.symbol)
    try:
        quote = await live_quote(instrument.symbol)
        order = await trading.place_order(
            session, user_id=user_id, instrument=instrument, side=body.side, type=body.type, quote=quote,
            qty=body.qty, notional=body.notional, limit_price=body.limit_price)
    except NoPriceError as e:
        raise HTTPException(status_code=503, detail=str(e))      # 503: can't trade right now, try again later
    except trading.OrderError as e:
        raise HTTPException(status_code=400, detail=str(e))      # 400: the order itself breaks a rule
    await trading.announce(order, "filled" if order.status == "filled" else "opened")
    return order_json(order)


@app.get("/orders")                               # GET /orders?status=open -> your orders, newest first
async def list_orders(status: str | None = None, session: AsyncSession = Depends(get_session),
                      user_id: int = Depends(current_user)):
    query = (select(Order).where(Order.user_id == user_id)
             .options(selectinload(Order.fills), selectinload(Order.instrument))
             .order_by(Order.submitted_at.desc(), Order.id.desc()))
    if status:
        query = query.where(Order.status == status)
    return [order_json(o) for o in await session.scalars(query)]


@app.get("/orders/{order_id}")                    # one order, with its fills' cost and profit worked out
async def get_order(order_id: int, session: AsyncSession = Depends(get_session),
                    user_id: int = Depends(current_user)):
    order = await session.scalar(select(Order).where(Order.id == order_id, Order.user_id == user_id)
                                 .options(selectinload(Order.fills), selectinload(Order.instrument)))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    position = build_position(trading.fill_rows(
        await trading.load_fills(session, user_id, order.instrument_id)))
    return order_json(order, position)


@app.delete("/orders/{order_id}")                 # cancel an open order
async def delete_order(order_id: int, session: AsyncSession = Depends(get_session),
                       user_id: int = Depends(current_user)):
    try:
        order = await trading.cancel_order(session, user_id, order_id)
    except trading.OrderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await trading.announce(order, "canceled")
    return order_json(order)


# ---------- live updates ----------

async def relay(websocket: WebSocket, channel: str):
    """Forward every message published on a Redis channel to one browser, until it disconnects."""
    await websocket.accept()                      # say yes to the browser's connection and keep it open
    pubsub = r.pubsub()                           # a separate Redis connection just for listening
    await pubsub.subscribe(channel)               # the channel stream_prices.py publishes to
    try:
        async for message in pubsub.listen():     # sleeps until Redis has a new message, then wakes up
            if message["type"] == "message":      # skip the "subscribed" confirmation, keep real data
                await websocket.send_text(message["data"])   # push it (already JSON) to the browser
    except (WebSocketDisconnect, RuntimeError):   # the browser closed the tab or went away
        pass
    finally:
        await pubsub.unsubscribe()                # stop listening, so Redis isn't sending to nobody
        await pubsub.aclose()                     # close this listener's Redis connection


@app.websocket("/ws/trades/{symbol}")             # ws://localhost:8000/ws/trades/BTC -> every trade, live
async def trades_ws(websocket: WebSocket, symbol: str):
    await relay(websocket, f"trades:{symbol.upper()}/USD")


@app.websocket("/ws/quotes/{symbol}")             # ws://localhost:8000/ws/quotes/BTC -> every bid/ask change, live
async def quotes_ws(websocket: WebSocket, symbol: str):
    await relay(websocket, f"quotes:{symbol.upper()}/USD")


@app.websocket("/ws/orders")                      # ws://localhost:8000/ws/orders -> your orders opening, filling, cancelling
async def orders_ws(websocket: WebSocket):
    await relay(websocket, f"orders:{current_user()}")
