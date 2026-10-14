import os                                         # read settings from the environment
import redis.asyncio as redis                     # async version of the redis package (already installed)
from dotenv import load_dotenv                    # loads your .env file

load_dotenv()                                     # read REDIS_URL from .env if it's there

r = redis.from_url(                               # one shared connection for the whole program
    os.getenv("REDIS_URL", "redis://localhost:6379/0"),   # falls back to your local Docker Redis
    decode_responses=True,                        # give back normal strings, not bytes
)