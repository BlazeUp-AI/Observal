import { useState, useEffect } from "react";

export async function apiFetch<T = unknown>(path: string, options?: RequestInit): Promise<T> {
  const apiKey = localStorage.getItem("observal_api_key") || "";
  const res = await fetch(path, {
    ...options,
    headers: { "X-API-Key": apiKey, ...options?.headers },
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export function useApiQuery<T = unknown>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiFetch<T>(path)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [path]);

  return { data, loading, error };
}
