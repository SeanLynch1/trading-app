import { useEffect, useState } from "react";
import { WS_URL } from "../config";
import { base } from "../lib/format";

// Live last-trade price for each symbol, e.g. { "BTC/USD": 67012.5 }.
// Trades can arrive many times a second, so the screen is updated at most 4 times a second.
export default function useLivePrices(symbols) {
  const [prices, setPrices] = useState({});
  const key = [...new Set(symbols)].sort().join(",");    // reconnect only when the set of symbols changes

  useEffect(() => {
    if (!key) return;
    const latest = {};
    const sockets = [];
    let stopped = false;

    for (const symbol of key.split(",")) {
      const connect = () => {
        const ws = new WebSocket(`${WS_URL}/ws/trades/${base(symbol)}`);
        ws.onmessage = (e) => { latest[symbol] = Number(JSON.parse(e.data).price); };
        ws.onclose = () => { if (!stopped) setTimeout(connect, 2000); };   // reconnect after a backend restart
        sockets.push(ws);
      };
      connect();
    }
    const timer = setInterval(() => {                     // copy the newest prices to the screen
      if (Object.keys(latest).length) setPrices((p) => ({ ...p, ...latest }));
    }, 250);

    return () => {
      stopped = true;
      clearInterval(timer);
      sockets.forEach((ws) => ws.close());
    };
  }, [key]);

  return prices;
}
