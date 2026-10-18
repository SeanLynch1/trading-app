import redis.asyncio as redis                     # async version of the redis package (already installed)
from config import REDIS_URL                      # settings come from one place (config.py)

r = redis.from_url(                               # one shared connection for the whole program
    REDIS_URL,
    decode_responses=True,                        # give back normal strings, not bytes
)
