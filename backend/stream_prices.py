import os                                         # read keys from the environment
import json                                       # turn text messages into Python data
import asyncio                                    # run the stream and the timer side by side
import websockets                                 # raw WebSocket client (installed with alpaca-py)
from dotenv import load_dotenv                    # loads your .env file
from redis_client import r                        # shared async Redis connection (redis_client.py)

load_dotenv()                                     # read ALPACA_API_KEY and ALPACA_SECRET_KEY from .env
URL = "wss://stream.data.alpaca.markets/v1beta3/crypto/us-1"   # Kraken US feed
SYMBOL = "BTC/USD"                                # change this to try another coin, e.g. "ETH/USD"

bid = None                                        # latest best price buyers are offering (from quotes)
ask = None                                        # latest best price sellers are asking (from quotes)

def new_stats():                                  # an empty scoreboard for one 60-second window
    return {"n": 0, "vol": 0.0, "buy": 0.0, "sell": 0.0, "value": 0.0,
            "open": None, "high": None, "low": None, "close": None}

stats = new_stats()                               # the scoreboard currently being filled

async def listen():
    global bid, ask, stats                        # lets us change the variables defined above
    try:
        await r.ping()                                       # fail early if Redis isn't running
        async with websockets.connect(URL) as ws:            # open the connection
            await ws.recv()                                  # skip the "connected" message
            await ws.send(json.dumps({                       # log in with your keys
                "action": "auth",
                "key": os.environ["ALPACA_API_KEY"],
                "secret": os.environ["ALPACA_SECRET_KEY"],
            }))
            print("auth:", await ws.recv(), flush=True)      # shows "authenticated" or the error reason
            await ws.send(json.dumps({                       # ask for trades AND quotes on the same connection
                "action": "subscribe",
                "trades": [SYMBOL],                          # executed trades
                "quotes": [SYMBOL],                          # best bid/ask prices (used for the spread)
            }))
            await ws.recv()                                  # skip the subscription confirmation
            async for message in ws:                         # wait for data as it arrives
                for item in json.loads(message):             # one message can hold several items
                    if item["T"] == "q":                     # "q" = quote update
                        bid, ask = item["bp"], item["ap"]    # remember the latest bid and ask (not printed)
                        await r.hset(f"quote:{SYMBOL}", mapping={   # save latest bid/ask to Redis
                            "bid": bid, "ask": ask, "time": item["t"],
                        })
                    elif item["T"] == "t":                   # "t" = a trade
                        price, size = item["p"], item["s"]   # price per bitcoin, bitcoin traded
                        is_buy = item.get("tks") == "B"      # taker side: B = the buyer started the trade
                        cost = price * size                  # amount in dollars

                        stats["n"] += 1                      # count the trade
                        stats["vol"] += size                 # total bitcoin traded
                        stats["buy" if is_buy else "sell"] += size   # bitcoin bought vs sold
                        stats["value"] += cost               # total dollars traded
                        if stats["open"] is None:            # first trade of the window = open price
                            stats["open"] = price
                        stats["high"] = price if stats["high"] is None else max(stats["high"], price)
                        stats["low"] = price if stats["low"] is None else min(stats["low"], price)
                        stats["close"] = price               # latest trade = close price

                        trade = {                            # the trade as a small dictionary
                            "time": item["t"],
                            "side": "BUY" if is_buy else "SELL",
                            "size": size,
                            "price": price,
                        }
                        await r.hset(f"last_trade:{SYMBOL}", mapping=trade)      # latest trade, for anyone who asks
                        await r.publish(f"trades:{SYMBOL}", json.dumps(trade))   # live broadcast, for anyone listening

                        spread = f"${ask - bid:.2f}" if bid and ask else "n/a"
                                                             # gap between best ask and best bid ("n/a" until the first quote)
                        print(
                            f"{item['t'][11:23]:<12} | "     # time of the trade, UTC, to the millisecond
                            f"{'BUY' if is_buy else 'SELL':<4} | "
                            f"{size:>12.8f} BTC | "          # size: 8 decimals, no scientific notation
                            f"${cost:>11,.2f} | "            # amount in dollars
                            f"${price:>10,.2f} | "           # price per bitcoin
                            f"{spread:>7}",                  # current spread
                            flush=True,
                        )
    except Exception as e:                        # show the reason instead of crashing silently
        print(f"failed: {e}", flush=True)

async def summary():                              # prints a recap every 60 seconds
    global stats
    while True:
        await asyncio.sleep(60)                   # wait a minute without freezing the stream
        s, stats = stats, new_stats()             # take the finished scoreboard, start a fresh one
        if s["n"] == 0:                           # nothing happened this minute
            print("--- last 60s: no trades ---", flush=True)
            continue
        vwap = s["value"] / s["vol"]              # average price, weighted by size
        buy_pct = 100 * s["buy"] / s["vol"]       # share of volume where buyers started the trade
        print(f"--- last 60s: {s['n']} trades | {s['vol']:.4f} BTC | ${s['value']:,.0f} | "
              f"buyers {buy_pct:.0f}% / sellers {100 - buy_pct:.0f}%", flush=True)
        print(f"    open ${s['open']:,.2f} | high ${s['high']:,.2f} | low ${s['low']:,.2f} | "
              f"close ${s['close']:,.2f} | VWAP ${vwap:,.2f}", flush=True)

async def main():
    await asyncio.gather(listen(), summary())     # run the stream and the summary timer together

print(f"{'TIME (UTC)':<12} | {'SIDE':<4} | {'SIZE (BTC)':>16} | {'AMOUNT (USD)':>12} | {'PRICE':>11} | {'SPREAD':>7}", flush=True)
                                                  # header line, same widths as the rows below it

try:
    asyncio.run(main())                           # start everything
except KeyboardInterrupt:                         # Ctrl+C
    print("Stream stopped.")