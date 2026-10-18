import CandleChart from "../components/CandleChart";
import PressureBar from "../components/PressureBar";
import QuotePanel from "../components/QuotePanel";
import TradesTable from "../components/TradesTable";
import useQuote from "../hooks/useQuote";
import useTrades from "../hooks/useTrades";

const SYMBOL = "BTC";                             // matches SYMBOL in stream_prices.py

// The live market view: bid/ask, chart, buy vs sell pressure, and every trade.
export default function MarketPage() {
  const { quote, error } = useQuote(SYMBOL);                        // live bid/ask
  const { trades, status, startedAt, now } = useTrades(SYMBOL);     // trades from the last 5 minutes

  return (
    <>
      <QuotePanel quote={quote} error={error} />
      <CandleChart symbol={SYMBOL} trades={trades} />
      <PressureBar trades={trades} startedAt={startedAt} now={now} />
      <TradesTable trades={trades} status={status} />
    </>
  );
}
