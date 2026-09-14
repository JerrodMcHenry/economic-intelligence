/**
 * The frontend's explanation content model (Increment #17C). Curated,
 * static, typed -- never AI-generated, never backend-mutating, and
 * never a source of canonical classification. See
 * docs/architecture/current-architecture.md's "Explainability
 * foundation" section for the full architectural boundary this
 * content must respect: canonical results flow INTO explanations,
 * explanations never flow into a canonical result.
 *
 * Only one content shape exists. There is no separate "result
 * explanation" type -- a result explanation (e.g. "why is momentum
 * MIXED?") is just one of these Explanation objects (looked up by the
 * backend's own already-classified value, e.g. `state`), presented
 * alongside backend-supplied evidence a component already has. See
 * components/inflation/WhyThisState.tsx.
 */
export interface Explanation {
  /** Stable, unique identifier -- for lookups and test targeting; never displayed. */
  id: string;
  /** Short label shown as the explanation's own heading. */
  title: string;
  /** Plain-English definition: what is this? */
  definition: string;
  /** Economic significance: why an investor/researcher/beginner would care. Education, never a trading recommendation. */
  whyItMatters?: string;
  /** A short, quiet source/methodology pointer (e.g. "Methodology: inflation_v1.0" or "Source: FRED release calendar"). */
  sourceNote?: string;
}
