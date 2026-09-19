import type { TargetResult } from "../../api/inflation.types";
import { FED_OBJECTIVE, TARGET_DEVIATION } from "../../content/explanations/inflation";
import { formatPercent, formatPercentagePoints, formatPeriod } from "../../lib/format";
import { ExplanationTrigger } from "../explanations/ExplanationTrigger";
import { EvidenceDisclosure } from "./EvidenceDisclosure";

/**
 * Headline PCE YoY against the Fed's objective and the resulting gap --
 * all three are backend values (`fed_objective_percent` is the
 * canonical objective exposed by the API; the UI never hardcodes its
 * own copy of it). No qualitative reading ("close"/"healthy"/"bad") is
 * added -- the backend model carries no such classification for this
 * section, so none is shown.
 */
export function TargetPanel({ target }: { target: TargetResult }) {
  return (
    <section aria-labelledby="target-heading">
      <h2 id="target-heading" className="text-sm font-medium text-fg-muted">
        Target / level
      </h2>
      {!target.available ? (
        <p className="mt-2 text-sm text-fg-muted">Target data unavailable.</p>
      ) : (
        <div className="mt-3 flex flex-wrap items-baseline gap-x-10 gap-y-2">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">Headline PCE</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums text-fg">{formatPercent(target.headline_pce_yoy)}</p>
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">Fed objective</p>
              <ExplanationTrigger explanation={FED_OBJECTIVE} />
            </div>
            <p className="mt-1 text-2xl font-semibold tabular-nums text-fg">{formatPercent(target.fed_objective_percent)}</p>
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">Gap</p>
              <ExplanationTrigger explanation={TARGET_DEVIATION} />
            </div>
            <p className="mt-1 text-2xl font-semibold tabular-nums text-fg">{formatPercentagePoints(target.target_gap_pp)}</p>
          </div>
        </div>
      )}
      <p className="mt-2 text-xs text-fg-muted">{formatPeriod(target.calculation_period)}</p>
      <div className="mt-3">
        <EvidenceDisclosure label="Headline PCE YoY" evidence={target.evidence} />
      </div>
    </section>
  );
}
