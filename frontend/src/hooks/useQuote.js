import { useEffect, useState } from "react";
import { API_URL, WS_URL } from "../config";
import useLiveSocket from "./useLiveSocket";

// Latest bid/ask: one GET for an instant first value, then live updates over the WebSocket.
export default function useQuote(symbol) {
  const [quote, setQuote] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {                               // 1. snapshot from GET /quote/{symbol}
    let cancelled = false;
    fetch(`${API_URL}/quote/${symbol}`)
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`No quote yet (${res.status}). Is stream_prices.py running?`))))
      .then((q) => { if (!cancelled) setQuote((current) => current ?? q); })   // don't overwrite a newer live quote
      .catch((err) => {
        if (!cancelled) setError(err.message === "Failed to fetch" ? "Can't reach the API. Is uvicorn running?" : err.message);
      });
    return () => { cancelled = true; };
  }, [symbol]);

  const status = useLiveSocket(`${WS_URL}/ws/quotes/${symbol}`, (q) => {   // 2. every update after that
    setQuote(q);
    setError(null);
  });

  return { quote, error, status };
}