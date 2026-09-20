import { useEffect, useState } from "react";

import { ApiError } from "./errors";
import { getMonitorHistoryDetail } from "./monitorHistory";
import type { HistoryMonitor, MonitorHistoryDetail } from "./monitorHistory.types";
import type { ApiResourceState } from "./useApiResource";

/**
 * One recorded result's detail, loaded on demand (Increment #32).
 *
 * A specialized sibling of `useApiResource`, with the same return
 * shape -- the precedent `useSinceLastVisit` set. Two reasons it cannot
 * simply be `useApiResource`:
 *
 * 1. **It is parameterized.** `useApiResource` deliberately does not
 *    track `fetcher` as an effect dependency, so an inline closure over
 *    `recordedResultId` would never refetch when the id changed.
 *
 * 2. **It must not fetch until asked.** Detail is only meaningful once
 *    a reader opens an entry. Fetching a detail per row on page load
 *    would issue a dozen requests nobody asked for -- so `enabled`
 *    gates the effect, and the resource stays idle until then.
 *
 * This is also why the page does not own this resource, unlike every
 * other one on Inflation and Labor: there is no single owner, there is
 * one per expandable row, created only when that row opens.
 */
export type MonitorHistoryDetailState = ApiResourceState<MonitorHistoryDetail> | { status: "idle" };

export function useMonitorHistoryDetail(
  monitor: HistoryMonitor,
  recordedResultId: number,
  enabled: boolean,
): MonitorHistoryDetailState {
  const [resolved, setResolved] = useState<ApiResourceState<MonitorHistoryDetail> | null>(null);

  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;

    getMonitorHistoryDetail(monitor, recordedResultId)
      .then((data) => {
        if (!cancelled) setResolved({ status: "success", data });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const apiError =
          error instanceof ApiError
            ? error
            : new ApiError("network", "Could not reach the server.", undefined, { cause: error });
        setResolved({ status: "error", error: apiError });
      });

    return () => {
      cancelled = true;
    };
  }, [monitor, recordedResultId, enabled]);

  // "loading" is DERIVED rather than stored: it is precisely "asked
  // for, nothing back yet", which the two existing pieces of state
  // already say between them. Storing it would mean a synchronous
  // setState inside the effect purely to describe a fact the render
  // can already see.
  if (!enabled) return resolved ?? { status: "idle" };
  return resolved ?? { status: "loading" };
}
