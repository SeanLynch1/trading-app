import { useState } from "react";
import useQuote from "../../hooks/useQuote";
import { postJSON } from "../../lib/api";
import { amount, base, money } from "../../lib/format";
import Modal from "./Modal";

const MIN_ORDER = 1;                              // dollars; the backend has the same rule (MIN_ORDER_VALUE)

// Buy/sell ticket: choose side, market or limit, and an amount in dollars or bitcoin; review; confirm.
// Prices are live from the stream; the backend re-checks every rule before anything is saved.
export default function OrderTicket({ symbol, initialSide = "buy", availableCash, availableQty, feeRate,
                                      marginable = false, onClose, onPlaced }) {
  const coin = base(symbol);
  const { quote } = useQuote(coin);
  const [side, setSide] = useState(initialSide);
  const [type, setType] = useState("market");
  const [unit, setUnit] = useState("USD");        // what the amount box means: dollars or bitcoin
  const [value, setValue] = useState("");
  const [limit, setLimit] = useState("");
  const [step, setStep] = useState("form");       // "form" -> "review" -> "sending" -> "done"
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const bid = quote ? Number(quote.bid) : null;
  const ask = quote ? Number(quote.ask) : null;
  const fee = Number(feeRate);

  // a limit box you haven't typed in shows today's price (bid when buying, ask when selling)
  const suggested = bid && ask ? (side === "buy" ? bid : ask).toFixed(2) : "";
  const limitValue = limit === "" ? suggested : limit;

  // What the order would do, worked out the same way as the backend (trading.place_order)
  const price = type === "market" ? (side === "buy" ? ask : bid) : Number(limitValue) || null;
  const entered = Number(value) || 0;
  let qty = 0;
  if (price && entered > 0) {
    qty = unit === "BTC" ? entered : side === "buy" ? entered / (price * (1 + fee)) : entered / price;
    qty = Math.floor(qty * 1e8) / 1e8;            // round down to 8 decimals, like the backend
  }
  const gross = qty * (price ?? 0);
  const feeAmount = gross * fee;
  const total = side === "buy" ? gross + feeAmount : gross - feeAmount;

  let problem = null;
  if (!quote) problem = "Waiting for a live price...";
  else if (type === "limit" && !(Number(limitValue) > 0)) problem = "Enter a limit price.";
  else if (entered <= 0) problem = null;          // empty box: no message yet, just a disabled button
  else if (gross < MIN_ORDER) problem = `The smallest order is ${money(MIN_ORDER)}.`;
  else if (side === "buy" && total > availableCash) problem = `Not enough cash: ${money(availableCash)} available.`;
  else if (side === "sell" && qty > availableQty) problem = `You have ${amount(availableQty)} ${coin} available to sell.`;
  const canReview = !problem && qty > 0;

  const setMax = () => {                          // fill the box with everything available
    if (side === "buy") { setUnit("USD"); setValue((Math.floor(availableCash * 100) / 100).toString()); }
    else { setUnit("BTC"); setValue(availableQty.toString()); }
  };

  const submit = async () => {
    setStep("sending");
    setError(null);
    try {
      const order = await postJSON("/orders", {
        symbol, side, type,
        ...(unit === "USD" ? { notional: value } : { qty: value }),   // dollars: the backend works out the exact amount
        ...(type === "limit" ? { limit_price: limitValue } : {}),
      });
      setResult(order);
      setStep("done");
      onPlaced?.(order);
    } catch (e) {
      setError(e.message);
      setStep("review");
    }
  };

  const verb = side === "buy" ? "Buy" : "Sell";

  return (
    <Modal title={`${verb} ${coin}`} onClose={onClose} level={2}>
      {step === "form" && (
        <div className="ticket">
          <div className="segmented" role="group" aria-label="Buy or sell">
            {["buy", "sell"].map((s) => (
              <button key={s} type="button" className={`seg ${s} ${side === s ? "active" : ""}`}
                      aria-pressed={side === s} onClick={() => { setSide(s); setLimit(""); }}>
                {s === "buy" ? "Buy" : "Sell"}
              </button>
            ))}
          </div>

          <div className="segmented small" role="group" aria-label="Order type">
            {[["market", "Market"], ["limit", "Limit"]].map(([t, label]) => (
              <button key={t} type="button" className={`seg ${type === t ? "active" : ""}`}
                      aria-pressed={type === t} onClick={() => setType(t)}>{label}</button>
            ))}
          </div>
          <p className="muted small-text ticket-hint">
            {type === "market"
              ? `Trades now at the best ${side === "buy" ? "ask" : "bid"}: ${money(price)}`
              : `Waits until the price ${side === "buy" ? "drops to" : "rises to"} your limit, then trades at it.`}
          </p>

          {type === "limit" && (
            <label className="field">
              <span className="label">Limit price (USD)</span>
              <input type="number" inputMode="decimal" min="0" step="0.01" value={limitValue}
                     onChange={(e) => setLimit(e.target.value)} />
            </label>
          )}

          <label className="field">
            <span className="label">Amount</span>
            <div className="amount-row">
              <input type="number" inputMode="decimal" min="0" step="any" placeholder="0" value={value}
                     onChange={(e) => setValue(e.target.value)} autoFocus />
              <div className="segmented tiny" role="group" aria-label="Amount in">
                {["USD", coin].map((u, i) => {
                  const key = i === 0 ? "USD" : "BTC";
                  return (
                    <button key={key} type="button" className={`seg ${unit === key ? "active" : ""}`}
                            aria-pressed={unit === key}
                            onClick={() => { setUnit(key); setValue(""); }}>{u}</button>
                  );
                })}
              </div>
              <button type="button" className="link-button" onClick={setMax}>Max</button>
            </div>
          </label>

          <div className="ticket-summary">
            <Row label={side === "buy" ? "You get" : "You sell"} value={`${amount(qty)} ${coin}`} />
            <Row label={`Fee (${(fee * 100).toFixed(2)}%)`} value={money(feeAmount)} />
            <Row label={side === "buy" ? "Total cost" : "You receive"} value={money(total)} strong />
            <Row label={side === "buy" ? "Cash available" : `${coin} available`}
                 value={side === "buy" ? money(availableCash) : `${amount(availableQty)} ${coin}`} muted />
            <Row label="Leverage" value={marginable ? "1×" : "1× · not available for crypto"} muted />
          </div>

          {problem && <p className="error">{problem}</p>}
          <button type="button" className={`primary-button ${side}`} disabled={!canReview}
                  onClick={() => { if (type === "limit") setLimit(limitValue); setStep("review"); }}>
            Review order
          </button>
        </div>
      )}

      {(step === "review" || step === "sending") && (
        <div className="ticket">
          <p className="review-lead">
            {verb} <b>{amount(qty)} {coin}</b> {type === "market" ? "at the market price" : `at ${money(price)} or better`}
          </p>
          <div className="ticket-summary">
            <Row label="Order" value={`${type === "market" ? "Market" : "Limit"} ${side}`} />
            <Row label={type === "market" ? "Price now" : "Limit price"} value={money(price)} />
            <Row label="Amount" value={`${amount(qty)} ${coin}`} />
            <Row label="Fee" value={money(feeAmount)} />
            <Row label={side === "buy" ? "Total cost" : "You receive"} value={money(total)} strong />
          </div>
          {type === "market" && <p className="muted small-text">The price can move slightly before your order fills.</p>}
          {error && <p className="error">{error}</p>}
          <div className="button-row">
            <button type="button" className="secondary-button" onClick={() => setStep("form")}
                    disabled={step === "sending"}>Back</button>
            <button type="button" className={`primary-button ${side}`} onClick={submit} disabled={step === "sending"}>
              {step === "sending" ? "Placing..." : `Confirm ${side}`}
            </button>
          </div>
        </div>
      )}

      {step === "done" && result && (
        <div className="ticket done">
          <div className={`done-mark ${side}`} aria-hidden="true">✓</div>
          {result.status === "filled" ? (
            <p className="review-lead">
              {side === "buy" ? "Bought" : "Sold"} <b>{amount(result.qty)} {coin}</b> at {money(Number(result.filled_avg_price))}
            </p>
          ) : (
            <p className="review-lead">
              Limit {side} placed. It will fill if the price reaches <b>{money(Number(result.limit_price))}</b>.
            </p>
          )}
          <button type="button" className="primary-button" onClick={onClose}>Done</button>
        </div>
      )}
    </Modal>
  );
}

function Row({ label, value, strong, muted }) {
  return (
    <div className={`summary-row ${muted ? "muted" : ""}`}>
      <span>{label}</span>
      <span className={strong ? "strong" : ""}>{value}</span>
    </div>
  );
}
