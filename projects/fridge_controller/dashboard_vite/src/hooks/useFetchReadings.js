import { useState, useEffect } from 'react';

export function useFetchReadings({ limit = 5000, since_s = null }) {
  const [data, setData] = useState({ rows: [], count: 0, ok: false, error: null });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let abortController = new AbortController();
    const fetchData = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        params.append('limit', limit.toString());
        if (since_s !== null) params.append('since_s', since_s.toString());
        const resp = await fetch(`/api/readings?${params.toString()}`, {
          signal: abortController.signal,
          cache: 'no-store',
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const json = await resp.json();
        setData({ ...json, ok: true, error: null });
      } catch (err) {
        if (err.name !== 'AbortError') {
          setData({ rows: [], count: 0, ok: false, error: err.message });
        }
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    const id = setInterval(fetchData, 2000);
    return () => {
      clearInterval(id);
      abortController.abort();
    };
  }, [limit, since_s]);

  return { ...data, loading };
}
