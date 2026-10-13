
import os
import asyncio
from dotenv import load_dotenv
from alpaca.data.live import CryptoDataStream

load_dotenv()

stream = CryptoDataStream(
    os.environ["ALPACA_API_KEY"],
    os.environ["ALPACA_SECRET_KEY"],
)

trade_count = 0

async def on_trade(trade):
    global trade_count
    trade_count += 1

    print(
        f"Trade #{trade_count}: "
        f"{trade.symbol} | "
        f"${trade.price:,.2f} | "
        f"Size: {trade.size} BTC | "
        f"{trade.timestamp}",
        flush=True,
    )

async def report_count():
    global trade_count

    while True:
        await asyncio.sleep(60)
        print(f"Trades received in the last minute: {trade_count}", flush=True)
        trade_count = 0

stream.subscribe_trades(on_trade, "BTC/USD")

print("Listening for Bitcoin trades...", flush=True)

async def main():
    asyncio.create_task(report_count())
    await stream._run_forever()

try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Stream stopped.")
