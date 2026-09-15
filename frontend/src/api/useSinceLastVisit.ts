/**
 * Data-lifecycle hook for Increment #25H's Since Last Visit V1 return
 * experience -- see docs/product/since-last-visit-v1.md (#25F),
 * specifically §5/§10-13/§91-93. A specialized sibling of
 * `useApiResource` (same three-state shape, same independent-loading
 * discipline), extended with the one behavior this feature needs that
 * a generic resource hook does not: reading a local checkpoint once
 * per request, and writing the server's own returned `through`
 * watermark back to storage -- but ONLY after a successful response
 * has been committed to this hook's own rendered state, never before,
 * and never as a reaction to the storage write itself (which would
 * otherwise trigger the exact refetch-loop the frozen contract's own
 * §13 warns against).
 *
 * The checkpoint is read exactly once per request (inside the fetch
 * effect, keyed only by `reloadToken`) -- never re-read reactively
 * after a write, so persisting `through` can never itself trigger a
 * new fetch.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { getSinceLastVisit } from "./sinceLastVisit";
import type { SinceLastVisitResponse } from "./sinceLastVisit.types";
import type { ApiResourceState } from "./useApiResource";
import { ApiError } from "./errors";
import { readSinceLastVisitCheckpoint, writeSinceLastVisitCheckpoint } from "../lib/sinceLastVisitCheckpoint";

export function useSinceLastVisit(): ApiResourceState<SinceLastVisitResponse> & { reload: () => void } {
  const [state, setState] = useState<ApiResourceState<SinceLastVisitResponse>>({ status: "loading" });
  const [reloadToken, setReloadToken] = useState(0);
  const persistedThroughRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });

    // Read once, for this request only -- contract §13's own explicit
    // requirement. `checkpoint` is never re-read after this point for
    // the duration of this fetch, and writing a NEW checkpoint later
    // (below) never causes this effect to re-run, since it does not
    // depend on storage state.
    const checkpoint = readSinceLastVisitCheckpoint();

    getSinceLastVisit(checkpoint?.through ?? null)
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadToken]);

  useEffect(() => {
    // Acknowledgement (contract §5/§6/§11/§92): the checkpoint is
    // written only once this hook's own state has actually transitioned
    // to "success" -- i.e., only after the response would be rendered,
    // never merely upon fetch resolution. Comparing against
    // `persistedThroughRef` (rather than writing unconditionally on
    // every "success" render) makes this idempotent and safe under
    // React Strict Mode's deliberate double-invocation of effects: the
    // second invocation sees the same `state.data.through` already
    // recorded in the ref and performs no redundant write.
    if (state.status === "success" && persistedThroughRef.current !== state.data.through) {
      writeSinceLastVisitCheckpoint(state.data.through);
      persistedThroughRef.current = state.data.through;
    }
    // API failure (§91) and the loading state never reach this branch
    // at all -- the checkpoint can only ever advance from a genuine
    // "success" state, never from an error or a still-pending request.
  }, [state]);

  const reload = useCallback(() => setReloadToken((token) => token + 1), []);

  return { ...state, reload };
}
