from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware   # lets the React app (another port) call this API
from redis_client import r                        # same shared async Redis connection the stream uses

app = FastAPI()                                   # the web app; uvicorn runs this object

app.add_middleware(                               # CORS: which websites may call this API from a browser
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],      # the Vite dev server running the React app
    allow_methods=["GET"],                        # read-only for now; add "POST" when orders arrive
    allow_headers=["*"],
)


@app.get("/quote/{symbol}")                       # GET /quote/BTC -> latest bid/ask, once (pull)
async def get_quote(symbol: str):
    quote = await r.hgetall(f"quote:{symbol.upper()}/USD")   # read the latest bid/ask the stream saved
    if not quote:                                 # nothing stored for that symbol (or stream not running)
        raise HTTPException(status_code=404, detail=f"No quote for {symbol.upper()}")
    return quote                                  # FastAPI turns the dictionary into JSON


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