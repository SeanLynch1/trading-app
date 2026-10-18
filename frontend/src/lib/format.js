// Number formatting used across the app. Money arrives from the API as strings (no precision lost), so convert with Number().

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export const money = (n) => (n == null || Number.isNaN(n) ? "–" : usd.format(n));

// +$12.34 / −$12.34 (a real minus sign, so the columns line up)
export const signedMoney = (n) => (n == null ? "–" : `${n >= 0 ? "+" : "−"}${usd.format(Math.abs(n))}`);

export const signedPct = (n) => (n == null || !Number.isFinite(n) ? "" : `${n >= 0 ? "+" : "−"}${Math.abs(n).toFixed(2)}%`);

// up to 8 decimals for bitcoin amounts, without trailing zeros: 0.00150000 -> 0.0015
export const amount = (n) => (n == null ? "–" : Number(n).toLocaleString("en-US", { maximumFractionDigits: 8 }));

// "green" for gains, "red" for losses, nothing for zero/unknown (classes from App.css)
export const tone = (n) => (n > 0 ? "buy" : n < 0 ? "sell" : "");

export const when = (iso) => (iso ? new Date(iso).toLocaleString(undefined, {
  day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
}) : "–");

export const base = (symbol) => symbol.split("/")[0];   // "BTC/USD" -> "BTC"
