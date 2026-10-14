// Where the FastAPI backend lives. Set VITE_API_URL in frontend/.env to change it (e.g. when deployed).
export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Same address, but ws:// instead of http:// (or wss:// instead of https://) for WebSockets.
export const WS_URL = API_URL.replace(/^http/, "ws");