import { useEffect, useRef, useState } from "react";
import { WS_URL } from "../config";
import useLiveSocket from "./useLiveSocket";

export const WINDOW_MS = 5 * 60 * 1000;           // rolling window: the last 5 minutes

// Every trade received in the last 5 minutes, oldest first.
// Each trade is dropped exactly 5 minutes after it arrived.
export default function useTrades(symbol) {
  const [trades, setTrades] = useState([]);
  const [startedAt] = useState(() => Date.now()); // when this page started listening
  const [now, setNow] = useState(() => Date.now());
  const nextId = useRef(0);                       // a unique id per trade, for React's list keys

  const status = useLiveSocket(`${WS_URL}/ws/trades/${symbol}`, (trade) => {
    const received = { ...trade, id: nextId.current++, receivedAt: Date.now() };
    setTrades((prev) => [...prev, received]);     // newest goes on the end
  });

  useEffect(() => {                               // once a second: drop trades older than 5 minutes
    const timer = setInterval(() => {
      const t = Date.now();
      const cutoff = t - WINDOW_MS;
      setNow(t);
      setTrades((prev) => (prev.length && prev[0].receivedAt < cutoff
        ? prev.filter((trade) => trade.receivedAt >= cutoff)
        : prev));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return { trades, status, startedAt, now };
}