import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";

interface FetchState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

// Runs an async loader on mount (and whenever `deps` change), exposing
// loading/error/data plus a manual reload. The loader is wrapped in useCallback
// by the caller via the deps array.
export function useFetch<T>(
  loader: () => Promise<T>,
  deps: unknown[] = [],
): FetchState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(loader, deps);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    run()
      .then(setData)
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Something went wrong"),
      )
      .finally(() => setLoading(false));
  }, [run]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, error, loading, reload };
}
