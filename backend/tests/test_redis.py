import pytest
from redis_client import r

# this function writes its own quotes to redis, reads it back, and checks it came back correctly.
@pytest.mark.asyncio
async def test_quote_round_trip():
    await r.hset("quote:TEST/USD", mapping={"bid": 100.0, "ask": 100.5})
    quote = await r.hgetall("quote:TEST/USD")
    assert quote == {"bid": "100.0", "ask": "100.5"}
    await r.delete("quote:TEST/USD")