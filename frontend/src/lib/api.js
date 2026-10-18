import { API_URL } from "../config";

// fetch() wrapper: returns the JSON, or throws an Error with the API's own message (e.g. "Not enough cash: ...").
async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    throw new Error("Can't reach the API. Is uvicorn running?");
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status})`);
  }
  return body;
}

export const getJSON = (path) => request(path);
export const postJSON = (path, data) => request(path, { method: "POST", body: JSON.stringify(data) });
export const deleteJSON = (path) => request(path, { method: "DELETE" });
