import BitcoinLogo from "./components/BitcoinLogo";
import QuotePanel from "./components/QuotePanel";
import PressureBar from "./components/PressureBar";
import TradesTable from "./components/TradesTable";
import useQuote from "./hooks/useQuote";
import useTrades from "./hooks/useTrades";
import "./App.css";

const SYMBOL = "BTC";                             // matches SYMBOL in stream_prices.py

export default function App() {
  const { quote, error } = useQuote(SYMBOL);                        // live bid/ask
  const { trades, status, startedAt, now } = useTrades(SYMBOL);     // trades from the last 5 minutes

  return (
    <main className="app">
      <header className="app-header">
        <BitcoinLogo size={44} />
        <div>
          <h1>Bitcoin</h1>
          <p className="subtitle">BTC/USD · paper trading · live data via Alpaca</p>
        </div>
      </header>

      <QuotePanel quote={quote} error={error} />
      <PressureBar trades={trades} startedAt={startedAt} now={now} />
      <TradesTable trades={trades} status={status} />
    </main>
  );
}