import { useEffect, useState } from "react";
import { WINDOW_MS } from "../hooks/useTrades";

const clock = (ms) => {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

// Buy vs sell volume over the rolling 5-minute window, as one bar where green meets red.
export default function PressureBar({ trades, startedAt, now }) {
  let buy = 0;
  let sell = 0;
  for (const t of trades) {
    if (t.side === "BUY") buy += Number(t.size);
    else sell += Number(t.size);
  }
  const total = buy + sell;
  const buyPct = total ? Math.round((buy / total) * 100) : 50;
  const sellPct = 100 - buyPct;

  const [ready, setReady] = useState(false);      // start both sides at 0%, then grow so they meet
  useEffect(() => {
    const frame = requestAnimationFrame(() => setReady(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  const elapsed = now - startedAt;
  const filling = elapsed < WINDOW_MS;

  return (
    <section className="card">
      <div className="card-header">
        <h2>Buy vs sell pressure</h2>
        <span className="muted small-text">
          {filling ? `Window filling: ${clock(elapsed)} / 5:00` : "Last 5 minutes"}
        </span>
      </div>

      <div className="pressure-labels">
        <span className="buy">BUY {total ? `${buyPct}%` : "–"}</span>
        <span className="sell">{total ? `${sellPct}%` : "–"} SELL</span>
      </div>

      <div className={`pressure-bar ${total ? "" : "empty"}`}>
        <div className="pressure-side pressure-buy" style={{ width: ready ? `${buyPct}%` : "0%" }} />
        <div className="pressure-side pressure-sell" style={{ width: ready ? `${sellPct}%` : "0%" }} />
        {ready && (
          <div className="pressure-seam" style={{ left: `${buyPct}%` }}>
            <span key={buyPct} className="pressure-clash" />
          </div>
        )}
      </div>

      <p className="muted small-text pressure-footer">
        {total
          ? `${trades.length.toLocaleString()} trades · ${buy.toFixed(4)} BTC bought · ${sell.toFixed(4)} BTC sold`
          : "Waiting for trades..."}
      </p>
    </section>
  );
}
