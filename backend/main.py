from fastapi import FastAPI, HTTPException        # FastAPI builds the web API; HTTPException sends error responses
from redis_client import r                        # same shared async Redis connection the stream uses
 
app = FastAPI()                                   # the web app; uvicorn runs this object
 
@app.get("/quote/{symbol}")                       # GET /quote/BTC -> calls get_quote(symbol="BTC")
async def get_quote(symbol: str):
    quote = await r.hgetall(f"quote:{symbol.upper()}/USD")   # read the latest bid/ask the stream saved
    if not quote:                                 # nothing stored for that symbol (or stream not running)
        raise HTTPException(status_code=404, detail=f"No quote for {symbol.upper()}")
    return quote                                  # FastAPI turns the dictionary into JSON
 