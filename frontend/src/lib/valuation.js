// Live value and P&L for a holding, from the parts the API sends and the latest price.
// (The backend explains these formulas in holding_json in main.py.)

export function valueHolding(h, livePrice) {
  const price = livePrice ?? (h.last_price != null ? Number(h.last_price) : null);
  const qty = Number(h.qty);
  const cost = Number(h.cost_basis);
  const realized = Number(h.realized);
  if (price == null) return { price: null, qty, value: null, totalPnl: null, totalPct: null, dailyPnl: null, dailyPct: null };

  const value = qty * price;
  const totalPnl = realized + value - cost;                // locked-in profit + paper profit
  let dailyPnl = null;
  let dailyPct = null;
  if (h.day_open_price != null) {
    const startValue = Number(h.qty_day_start) * Number(h.day_open_price);
    const netFlow = Number(h.day_net_flow);               // money put into this holding today
    dailyPnl = value - startValue - netFlow;
    const base = startValue + Number(h.day_bought ?? 0);   // what was at stake today: held at midnight + bought since
    dailyPct = base > 0 ? (dailyPnl / base) * 100 : null;
  }
  return {
    price, qty, value, totalPnl,
    totalPct: cost > 0 ? (totalPnl / cost) * 100 : null,
    dailyPnl, dailyPct,
  };
}

export function valuePortfolio(portfolio, prices) {
  const holdings = portfolio.holdings.map((h) => ({ ...h, live: valueHolding(h, prices[h.symbol]) }));
  const invested = holdings.reduce((sum, h) => sum + (h.live.value ?? 0), 0);
  const cash = Number(portfolio.cash);
  const balance = cash + invested;
  const deposited = Number(portfolio.net_deposited);
  const totalPnl = balance - deposited;                    // everything you have, minus everything you put in
  const known = holdings.filter((h) => h.live.dailyPnl != null);
  const dailyPnl = known.length ? known.reduce((sum, h) => sum + h.live.dailyPnl, 0) : null;
  return {
    holdings, invested, cash, balance, deposited, totalPnl,
    totalPct: deposited > 0 ? (totalPnl / deposited) * 100 : null,
    dailyPnl,
    dailyPct: dailyPnl != null && balance - dailyPnl > 0 ? (dailyPnl / (balance - dailyPnl)) * 100 : null,
    available: Number(portfolio.available_cash),
    reserved: Number(portfolio.reserved_cash),
  };
}
