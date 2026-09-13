import { useCallback, useEffect, useState } from "react";

import { ApiError } from "./errors";

/**
 * The state of one independent network resource: loading, successfully
 * parsed data, or an infrastructure-level `ApiError` (never an
 * economic-data state -- a successful 200 with, e.g.,
 * `state: "INSUFFICIENT_DATA"` is `{ status: "success" }` here; that
 * distinction is exactly what `ApiError` (see ./errors.ts) exists to
 * preserve).
 */
export type ApiResourceState<T> =
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: ApiError };

/**
 * Load one API resource independently of any other. Two components on
 * the same page each calling this with a different `fetcher` load and
 * fail completely independently -- neither fabricates data for, nor is
 * blocked by, the other. `fetcher` is expected to be a stable
 * reference (a module-level function, as `getInflationMonitor`/
 * `getInflationWhatChanged` are) -- it is intentionally not tracked as
 * an effect dependency, only `reload()` re-triggers a fetch, so an
 * inline arrow function passed here will not cause a refetch loop, but
 * also will not itself trigger a reload if its closed-over values
 * change; callers needing that should depend on `reload` instead.
 */
export function useApiResource<T>(fetcher: () => Promise<T>): ApiResourceState<T> & { reload: () => void } {
  const [state, setState] = useState<ApiResourceState<T>>({ status: "loading" });
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });

    fetcher()
      .then((data) => {
        if (!cancelled) setState({ status: "success", data });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const apiError =
          error instanceof ApiError ? error : new ApiError("network", "Could not reach the server.", undefined, { cause: error });
        setState({ status: "error", error: apiError });
      });

    return () => {
      cancelled = true;
    };
    // `fetcher` is deliberately not a dependency -- see the doc comment
    // above; `reloadToken` is the only intended re-fetch trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadToken]);

  const reload = useCallback(() => setReloadToken((token) => token + 1), []);

  return { ...state, reload };
}
