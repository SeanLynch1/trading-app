import { useEffect, useState } from "react";
import useApi from "../../hooks/useApi";
import { deleteJSON } from "../../lib/api";
import { amount, base, money, signedMoney, signedPct, tone, when } from "../../lib/format";
import { valueHolding } from "../../lib/valuation";
import Modal from "./Modal";
import TradeDetail from "./TradeDetail";

// Everything about one holding: position, today's and all-time P&L, open orders and past trades.
// refreshKey changes whenever an order event arrives, so this reloads when an order fills or is cancelled.
export default function AssetPanel({ symbol, livePrice, refreshKey, onClose, onTrade }) {
  const coin = base(symbol);
  const { data, error, reload } = useApi(`/holdings/${coin}`);
  const [selectedId, setSelectedId] = useState(null);
  const [canceling, setCanceling] = useState(null);
  const [cancelError, setCancelError] = useState(null);

  useEffect(() => { if (refreshKey) reload(); }, [refreshKey, reload]);

  const cancel = async (order) => {
    setCanceling(order.id);
    setCancelError(null);
    try {
      await deleteJSON(`/orders/${order.id}`);
      reload();
    } catch (e) {
      setCancelError(e.message);
    } finally {
      setCanceling(null);
    }
  };

  if (!data) {
    return (
      <Modal title={coin} onClose={onClose} wide>
        <p className={error ? "error" : "muted"}>{error || "Loading..."}</p>
      </Modal>
    );
  }

  const h = data.holding;
  const live = valueHolding(h, livePrice);
  const open = data.orders.filter((o) => o.status === "open");
  const past = data.orders.filter((o) => o.status !== "open");
  const selected = data.orders.find((o) => o.id === selectedId);

  return (
    <Modal title={`${h.name} · ${coin}`} onClose={onClose} wide>
      <div className="asset">
        <div className="asset-hero">
          <div>
            <span className="label">Value</span>
            <span className="asset-value">{money(live.value)}</span>
            <span className="muted small-text">
              {amount(h.qty)} {coin} · last price {money(live.price)}
            </span>
          </div>
          <span className={`position-pill ${live.qty > 0 ? "long" : ""}`}>{live.qty > 0 ? "Long" : "No position"}</span>
        </div>

        <div className="stat-grid">
          <Stat label="Today" value={signedMoney(live.dailyPnl)} sub={signedPct(live.dailyPct)} tone={tone(live.dailyPnl)} />
          <Stat label="All-time P&L" value={signedMoney(live.totalPnl)} sub={signedPct(live.totalPct)} tone={tone(live.totalPnl)} />
          <Stat label="Avg. cost" value={h.avg_price ? money(Number(h.avg_price)) : "–"} sub="per coin, incl. fees" />
          <Stat label="Locked in" value={signedMoney(Number(h.realized))} sub={`fees paid ${money(Number(h.fees))}`}
                tone={tone(Number(h.realized))} />
        </div>

        <div className="button-row">
          <button type="button" className="primary-button buy" onClick={() => onTrade("buy")}>Buy</button>
          <button type="button" className="primary-button sell" onClick={() => onTrade("sell")}
                  disabled={!(live.qty > 0)}>Sell</button>
        </div>
        {!h.shortable && <p className="muted small-text">Crypto can only be held long: you can sell what you own, not short it.</p>}

        {open.length > 0 && (
          <section>
            <h3 className="section-title">Open orders</h3>
            {cancelError && <p className="error">{cancelError}</p>}
            <ul className="order-list">
              {open.map((o) => (
                <li key={o.id}>
                  <button type="button" className="order-row" onClick={() => setSelectedId(o.id)}>
                    <span className={`side-tag ${o.side}`}>{o.side}</span>
                    <span>Limit {money(Number(o.limit_price))}</span>
                    <span className="muted">{amount(o.qty)} {coin}</span>
                    <span className="muted small-text">{when(o.submitted_at)}</span>
                  </button>
                  <button type="button" className="link-button danger" onClick={() => cancel(o)}
                          disabled={canceling === o.id}>
                    {canceling === o.id ? "Cancelling..." : "Cancel"}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section>
          <h3 className="section-title">Trade history</h3>
          {past.length === 0 && <p className="muted small-text">No trades yet.</p>}
          <ul className="order-list">
            {past.map((o) => (
              <li key={o.id}>
                <button type="button" className="order-row" onClick={() => setSelectedId(o.id)}>
                  <span className={`side-tag ${o.side}`}>{o.side}</span>
                  <span>{o.status === "filled" ? money(Number(o.filled_avg_price)) : "Canceled"}</span>
                  <span className="muted">{amount(o.qty)} {coin}</span>
                  <span className="muted small-text">{when(o.filled_at ?? o.canceled_at ?? o.submitted_at)}</span>
                  <span className="chevron" aria-hidden="true">›</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {selected && (
        <TradeDetail order={selected} livePrice={live.price} onClose={() => setSelectedId(null)}
                     onCancel={async (o) => { await cancel(o); setSelectedId(null); }}
                     canceling={canceling === selected.id} />
      )}
    </Modal>
  );
}

function Stat({ label, value, sub, tone: color = "" }) {
  return (
    <div className="stat">
      <span className="label">{label}</span>
      <span className={`stat-value ${color}`}>{value}</span>
      {sub && <span className={`small-text ${color || "muted"}`}>{sub}</span>}
    </div>
  );
}
