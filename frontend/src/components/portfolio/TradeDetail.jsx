import { amount, base, money, signedMoney, signedPct, tone, when } from "../../lib/format";
import Modal from "./Modal";

// One order in detail. For a filled buy: what it cost, how much you still hold, and its profit so far.
// For a filled sell: what it paid and its profit compared with what that bitcoin cost (first-in-first-out).
export default function TradeDetail({ order, livePrice, onClose, onCancel, canceling }) {
  const coin = base(order.symbol);
  const filled = order.status === "filled";
  const sum = (key) => order.fills.reduce((s, f) => s + Number(f[key] ?? 0), 0);

  const qty = Number(order.qty);
  const fee = sum("fee");
  const cashFlow = sum("cash_flow");              // buy: spent incl. fee; sell: received after fee
  const realized = sum("realized");
  const remaining = sum("remaining");             // buy: bitcoin from this buy still held
  const costLeft = sum("cost_left");
  const held = order.side === "buy" && filled && livePrice != null;
  const heldValue = held ? remaining * livePrice : null;
  const unrealized = held ? heldValue - costLeft : 0;
  const pnl = filled ? realized + unrealized : null;
  const basis = order.side === "buy" ? cashFlow : cashFlow - realized;   // what the bitcoin in this trade cost
  const pct = pnl != null && basis > 0 ? (pnl / basis) * 100 : null;

  const title = `${order.side === "buy" ? "Buy" : "Sell"} ${coin} · ${order.type}`;

  return (
    <Modal title={title} onClose={onClose} level={1}>
      <div className="detail">
        <div className="detail-hero">
          <span className={`status-pill ${order.status}`}>{order.status}</span>
          {filled && (
            <>
              <span className={`detail-pnl ${tone(pnl)}`}>{signedMoney(pnl)}</span>
              <span className={`muted ${tone(pnl)}`}>{signedPct(pct)}</span>
            </>
          )}
        </div>

        <dl className="detail-list">
          <Item label={filled ? `${order.side === "buy" ? "Bought" : "Sold"} at` : "Limit price"}
                value={money(Number(filled ? order.filled_avg_price : order.limit_price))} />
          <Item label="Quantity" value={`${amount(qty)} ${coin}`} />
          {filled && <Item label="Fee" value={money(fee)} />}
          {filled && <Item label={order.side === "buy" ? "Total cost" : "Received"} value={money(cashFlow)} />}
          {filled && order.side === "buy" && (
            <>
              <Item label="Still held" value={`${amount(remaining)} ${coin}`} />
              {remaining < qty && <Item label="Since sold" value={`${amount(qty - remaining)} ${coin}`} />}
              {heldValue != null && <Item label="Value now" value={money(heldValue)} />}
              {remaining > 0 && <Item label="Paper profit (held part)" value={signedMoney(unrealized)} className={tone(unrealized)} />}
              {remaining < qty && <Item label="Locked-in profit (sold part)" value={signedMoney(realized)} className={tone(realized)} />}
            </>
          )}
          {filled && order.side === "sell" && (
            <>
              <Item label="That bitcoin cost" value={money(basis)} />
              <Item label="Profit on the sale" value={signedMoney(realized)} className={tone(realized)} />
            </>
          )}
          <Item label="Placed" value={when(order.submitted_at)} />
          {filled && <Item label="Filled" value={`${when(order.filled_at)} · ${order.fills[0]?.liquidity ?? ""}`} />}
          {order.status === "canceled" && <Item label="Canceled" value={when(order.canceled_at)} />}
        </dl>

        {filled && <p className="muted small-text">Fees are included in cost and profit. Sells use up your oldest bitcoin first.</p>}

        {order.status === "open" && (
          <button type="button" className="secondary-button danger" onClick={() => onCancel(order)} disabled={canceling}>
            {canceling ? "Cancelling..." : "Cancel order"}
          </button>
        )}
      </div>
    </Modal>
  );
}

function Item({ label, value, className = "" }) {
  return (
    <div className="detail-item">
      <dt>{label}</dt>
      <dd className={className}>{value}</dd>
    </div>
  );
}
