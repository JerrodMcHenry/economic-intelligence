/**
 * TypeScript mirror of the backend's MacroChipz Analyst contracts
 * (`app/models/analyst.py`, Increment #33), copied field-for-field from
 * the real backend models (verified by inspection, not guessed).
 *
 * Note what the REQUEST type does not contain: no state, no evidence, no
 * numbers, no context packet. A browser names a context; the server
 * builds it. If this type ever grew a `canonical_state` field, a client
 * could make the Analyst explain an economy that does not exist -- so
 * the absence is the contract, not an omission.
 *
 * Do not add, rename, or infer a field that isn't in those models.
 */

export type AnalystContextType = "INFLATION" | "LABOR" | "RATES" | "MONITOR_HISTORY";

export type AnalystEvidenceKind = "OBSERVATION" | "METRIC" | "STATE" | "CHANGE" | "COMPARISON" | "PROVENANCE";

/** What the browser may say. Deliberately tiny. */
export interface AnalystContextRef {
  type: AnalystContextType;
  recorded_result_id?: number;
  monitor?: "inflation" | "labor";
}

export interface AnalystExplainRequest {
  context: AnalystContextRef;
  question: string;
}

/**
 * One validated evidence reference. Every field here was resolved from
 * MacroChipz's own context packet, never authored by the model -- a
 * reference the packet did not contain never reaches this array.
 */
export interface AnalystEvidenceReference {
  id: string;
  kind: AnalystEvidenceKind;
  label: string;
  value: string | null;
  detail: string | null;
}

export interface AnalystMetadata {
  context_version: string;
  prompt_version: string;
  model: string;
  evidence_references_returned: number;
  evidence_references_dropped: number;
}

export interface AnalystExplainResponse {
  answer: string;
  evidence: AnalystEvidenceReference[];
  limitations: string[];
  metadata: AnalystMetadata;
}

export interface AnalystAvailability {
  available: boolean;
  reason: "NOT_CONFIGURED" | null;
}
