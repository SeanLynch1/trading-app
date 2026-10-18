import { useEffect, useRef, useState } from "react";

// Opens a WebSocket, calls onMessage with each parsed message, and reconnects
// automatically if the connection drops (e.g. when uvicorn --reload restarts).
export default function useLiveSocket(url, onMessage) {
  const [status, setStatus] = useState("connecting");   // "connecting" | "open" | "closed"
  const handler = useRef(onMessage);
  handler.current = onMessage;                    // always call the latest version of onMessage

  useEffect(() => {
    let ws;
    let retryTimer;
    let stopped = false;

    function connect() {
      setStatus("connecting");
      ws = new WebSocket(url);
      ws.onopen = () => setStatus("open");
      ws.onmessage = (event) => handler.current(JSON.parse(event.data));
      ws.onclose = () => {
        if (stopped) return;                      // closed on purpose, don't reconnect
        setStatus("closed");
        retryTimer = setTimeout(connect, 2000);   // try again in 2 seconds
      };
    }

    connect();
    return () => {                                // runs when the component goes away
      stopped = true;
      clearTimeout(retryTimer);
      ws.close();
    };
  }, [url]);

  return status;
}