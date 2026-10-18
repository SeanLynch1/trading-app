import { useLayoutEffect, useRef } from "react";

const MAX_ROWS = 200;                             // how many trades the table shows
const STATUS_TEXT = { open: "Live", connecting: "Connecting...", closed: "Disconnected, retrying..." };

// Scrollable list of trades, newest at the bottom. Follows new trades unless you scroll up.
export default function TradesTable({ trades, status }) {
  const box = useRef(null);
  const followBottom = useRef(true);              // true while the user is at (or near) the bottom
  const rows = trades.slice(-MAX_ROWS);

  useLayoutEffect(() => {                         // after each update, keep the newest trade in view
    if (box.current && followBottom.current) box.current.scrollTop = box.current.scrollHeight;
  }, [trades]);

  function handleScroll() {                       // the user scrolled: are they still at the bottom?
    const el = box.current;
    followBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  }

  return (
    <section className="card">
      <div className="card-header">
        <h2>Live trades</h2>
        <span className={`status ${status === "open" ? "live" : ""}`}>{STATUS_TEXT[status]}</span>
      </div>

      <div className="trades-scroll" ref={box} onScroll={handleScroll}>
        <table>
          <thead>
            <tr><th>Time (UTC)</th><th>Side</th><th>Size (BTC)</th><th>Price</th></tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.id}>
                <td>{t.time.slice(11, 23)}</td>
                <td className={t.side === "BUY" ? "buy" : "sell"}>{t.side}</td>
                <td>{Number(t.size).toFixed(8)}</td>
                <td>${Number(t.price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="muted empty-row">Waiting for trades...</p>}
      </div>
    </section>
  );
}