import os                                         # read settings from the environment
from dotenv import load_dotenv                    # loads your .env file

load_dotenv()                                     # runs once per program, the first time anything imports config

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")      # None if missing, so importing never crashes (e.g. in CI)
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")   # falls back to your local Docker Redis
DATABASE_URL = os.getenv(                         # falls back to the Postgres in docker-compose.yml
    "DATABASE_URL",                               # on AWS: the RDS address, usually with ?ssl=require on the end
    "postgresql+asyncpg://trader:trader@localhost:5432/trading",
)
STARTING_CASH = os.getenv("STARTING_CASH", "100000")   # your paper account's starting balance, recorded as the first deposit
FEE_RATE = os.getenv("FEE_RATE", "0.0025")        # simulated fee per trade: 0.0025 = 0.25% (like Kraken); "0" for none
