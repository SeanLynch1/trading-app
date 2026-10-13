import os                                         # lets us read environment variables (where your keys live)
from dotenv import load_dotenv                    # reads the .env file and loads its values
from alpaca.trading.client import TradingClient   # Alpaca's official client for account info and orders

load_dotenv()                                     # load ALPACA_API_KEY and ALPACA_SECRET_KEY from .env into environment variables

client = TradingClient(
    os.environ["ALPACA_API_KEY"],                 # your key ID; raises an error if missing, which is what we want
    os.environ["ALPACA_SECRET_KEY"],              # your secret key
    paper=True,                                   # IMPORTANT: use the paper (fake money) environment, never a live account
)

account = client.get_account()                    # ask Alpaca for your account details over the internet
print(account.status, account.cash, account.equity, account.buying_power)   # status should be ACTIVE; paper accounts start with fake money