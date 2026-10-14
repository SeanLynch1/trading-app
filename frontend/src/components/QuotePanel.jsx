import { useEffect, useRef, useState } from "react";

const money = (n) => `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// A number that briefly flashes green when it goes up and red when it goes down.
function TickValue({ value, className = "" }) {
  const previous = useRef(value);
  const [direction, setDirection] = useState("");

  useEffect(() => {
    if (value > previous.current) setDirection("tick-up");
    else if (value < previous.current) setDirection("tick-down");
    previous.current = value;
    const timer = setTimeout(() => setDirection(""), 400);
    return () => clearTimeout(timer);
  }, [value]);

  return <span className={`value ${className} ${direction}`}>{money(value)}</span>;
}

// Latest bid / ask / spread. Updates live as the stream publishes new quotes.
export default function QuotePanel({ quote, error }) {
  if (!quote) {
    return (
      <section className="card">
        <p className={error ? "error" : "muted"}>{error || "Loading quote..."}</p>
      </section>
    );
  }

  const bid = Number(quote.bid);
  const ask = Number(quote.ask);

  return (
    <section className="card">
      <div className="quote-grid">
        <div><span className="label">Bid</span><TickValue value={bid} className="buy" /></div>
        <div><span className="label">Ask</span><TickValue value={ask} className="sell" /></div>
        <div><span className="label">Spread</span><span className="value">{money(ask - bid)}</span></div>
        <div><span className="label">As of (UTC)</span><span className="value small">{quote.time.slice(11, 23)}</span></div>
      </div>
    </section>
  );
}