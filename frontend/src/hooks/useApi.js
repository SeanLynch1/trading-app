import { useCallback, useEffect, useState } from "react";
import { getJSON } from "../lib/api";

// Loads JSON from the API (e.g. "/portfolio") and gives back { data, error, reload }.
// Pass null as the path to load nothing (e.g. while a panel is closed).
export default function useApi(path) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [version, setVersion] = useState(0);              // bump to load again
  const reload = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    getJSON(path)
      .then((d) => { if (!cancelled) { setData(d); setError(null); } })
      .catch((e) => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };                   // ignore a slow reply if the path changed meanwhile
  }, [path, version]);

  return { data, error, reload };
}
