import { useCallback, useEffect, useState } from "react";
import BitcoinLogo from "../components/BitcoinLogo";
import AssetPanel from "../components/portfolio/AssetPanel";
import OrderTicket from "../components/portfolio/OrderTicket";
import useApi from "../hooks/useApi";
import useLivePrices from "../hooks/useLivePrices";
import useOrderEvents from "../hooks/useOrderEvents";
import { amount, base, money, signedMoney, signedPct, tone } from "../lib/format";
import { valuePortfolio } from "../lib/valuation";
import "../portfolio.css";

const DEFAULT_SYMBOL = "BTC/USD";                 // what the Invest button trades when nothing is selected

// The home page: balance and P&L on top, holdings in the middle, deposits and cash at the bottom,
// and an Invest button floating over everything.
export default function PortfolioPage() {
  const { data, error, reload } = useApi("/portfolio");
  const prices = useLivePrices(data ? [DEFAULT_SYMBOL, ...data.holdings.map((h) => h.symbol)] : []);
  const [selected, setSelected] = useState(null);         // the holding whose panel is open
  const [ticket, setTicket] = useState(null);             // { symbol, side } while the order ticket is open
  const [refreshKey, setRefreshKey] = useState(0);        // bumped on every order event, so open panels reload
  const [toast, setToast] = useState(null);

  useOrderEvents(useCallback((e) => {                     // an order opened, filled or was cancelled
    reload();
    setRefreshKey((k) => k + 1);
    if (e.event === "filled") setToast(`Order ${e.order_id} filled`);
  }, [reload]));

  useEffect(() => {                                       // hide the notice after a few seconds
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  if (!data) {
    return <section className="card"><p className={error ? "error" : "muted"}>{error || "Loading portfolio..."}</p></section>;
  }

  const p = valuePortfolio(data, prices);
  const holdingFor = (symbol) => p.holdings.find((h) => h.symbol === symbol);
  const ticketHolding = ticket && holdingFor(ticket.symbol);
  const availableQty = ticketHolding ? Math.max(0, Number(ticketHolding.qty) - Number(ticketHolding.qty_reserved)) : 0;

  return (
    <div className="portfolio">
      <section className="card balance-card">
        <span className="label">Portfolio balance</span>
        <span className="balance">{money(p.balance)}</span>
        <div className="balance-pnl">
          <span className={tone(p.dailyPnl)}>{signedMoney(p.dailyPnl)} {signedPct(p.dailyPct)} <span className="muted">today</span></span>
          <span className={tone(p.totalPnl)}>{signedMoney(p.totalPnl)} {signedPct(p.totalPct)} <span className="muted">all time</span></span>
        </div>
        <div className="balance-split">
          <div><span className="label">Invested</span><span>{money(p.invested)}</span></div>
          <div><span className="label">Cash</span><span>{money(p.cash)}</span></div>
          <div><span className="label">P&L</span><span className={tone(p.totalPnl)}>{signedMoney(p.totalPnl)}</span></div>
        </div>
      </section>

      <section className="card holdings-card">
        <div className="card-header"><h2>Holdings</h2></div>
        {p.holdings.length === 0 ? (
          <p className="muted empty-holdings">You don't own anything yet. Press <b>Invest</b> to buy your first bitcoin.</p>
        ) : (
          <div className="holdings-table" role="table" aria-label="Holdings">
            <div className="holdings-head" role="row">
              <span role="columnheader">Asset</span>
              <span role="columnheader">Today</span>
              <span role="columnheader">All time</span>
              <span role="columnheader">Value</span>
            </div>
            {p.holdings.map((h) => (
              <button key={h.symbol} type="button" className="holding-row" role="row" onClick={() => setSelected(h.symbol)}>
                <span className="holding-name" role="cell">
                  {h.asset_class === "crypto" && base(h.symbol) === "BTC" ? <BitcoinLogo size={30} /> : <span className="asset-dot" />}
                  <span>
                    <b>{base(h.symbol)}</b>
                    <span className="muted small-text">{amount(h.qty)} · {h.name}</span>
                  </span>
                </span>
                <span role="cell" className={tone(h.live.dailyPnl)}>
                  {signedMoney(h.live.dailyPnl)}<span className="small-text">{signedPct(h.live.dailyPct)}</span>
                </span>
                <span role="cell" className={tone(h.live.totalPnl)}>
                  {signedMoney(h.live.totalPnl)}<span className="small-text">{signedPct(h.live.totalPct)}</span>
                </span>
                <span role="cell" className="holding-value">{money(h.live.value)}</span>
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="card cash-card">
        <div><span className="label">Total deposited</span><span className="cash-value">{money(p.deposited)}</span></div>
        <div>
          <span className="label">Cash available</span>
          <span className="cash-value">{money(p.available)}</span>
          {p.reserved > 0 && <span className="muted small-text">+ {money(p.reserved)} held for open orders</span>}
        </div>
      </section>

      <div className="invest-dock">
        <button type="button" className="invest-button" onClick={() => setTicket({ symbol: DEFAULT_SYMBOL, side: "buy" })}>
          Invest
        </button>
      </div>

      {selected && (
        <AssetPanel symbol={selected} livePrice={prices[selected]} refreshKey={refreshKey}
                    onClose={() => setSelected(null)} onTrade={(side) => setTicket({ symbol: selected, side })} />
      )}

      {ticket && (
        <OrderTicket symbol={ticket.symbol} initialSide={ticket.side} availableCash={p.available}
                     availableQty={availableQty} feeRate={data.fee_rate} marginable={ticketHolding?.marginable}
                     onClose={() => setTicket(null)} onPlaced={() => { reload(); setRefreshKey((k) => k + 1); }} />
      )}

      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}
