import { apiGet, apiPost } from "./client";
import type {
  AnalystAvailability,
  AnalystContextRef,
  AnalystExplainResponse,
} from "./analyst.types";

/**
 * MacroChipz Analyst client (Increment #33).
 *
 * Two calls, both bounded. `askAnalyst` sends only a context REFERENCE
 * and the user's question -- never state, evidence, or numbers. The
 * server resolves the canonical intelligence itself, which is what stops
 * a client dictating the facts the Analyst then explains.
 */

/** Stable module-level fetcher for `useApiResource`. */
export function getAnalystAvailability(): Promise<AnalystAvailability> {
  return apiGet<AnalystAvailability>("/api/v1/analyst/availability");
}

export function askAnalyst(context: AnalystContextRef, question: string): Promise<AnalystExplainResponse> {
  return apiPost<AnalystExplainResponse>("/api/v1/analyst/explain", { context, question });
}
