import { describe, expect, it } from "vitest";

import {
  employmentConditionLabel,
  employmentConditionLabelOrRaw,
  employmentMomentumLabel,
  employmentMomentumLabelOrRaw,
  employmentStateLabel,
  employmentStateLabelOrRaw,
  employmentStateTone,
  isJobCountField,
  isPercentagePointDeltaField,
  laborChangeComponentLabelOrRaw,
  laborChangeFieldLabel,
  laborStateLabel,
  laborStateLabelOrRaw,
  laborStateTone,
  unemploymentStateLabel,
  unemploymentStateLabelOrRaw,
  unemploymentStateTone,
} from "./laborLabels";

describe("laborStateTone -- no directional color-coding (docs/architecture/labor-ui-v1.md §8)", () => {
  it("never maps INSUFFICIENT_DATA to a directional tone -- it must read as unavailable evidence, not a direction", () => {
    expect(laborStateTone("INSUFFICIENT_DATA")).toBe("unavailable");
  });

  it("gives MIXED the caution tone, matching Inflation's own MIXED precedent", () => {
    expect(laborStateTone("MIXED")).toBe("caution");
  });

  it.each(["STRENGTHENING", "COOLING", "STABLE"] as const)(
    "gives %s the same neutral tone -- no bullish/bearish color implication",
    (state) => {
      expect(laborStateTone(state)).toBe("neutral");
    },
  );
});

describe("laborStateLabel", () => {
  it("renders every state with a readable, typographically-transformed-only label", () => {
    expect(laborStateLabel("STRENGTHENING")).toBe("Strengthening");
    expect(laborStateLabel("COOLING")).toBe("Cooling");
    expect(laborStateLabel("STABLE")).toBe("Stable");
    expect(laborStateLabel("MIXED")).toBe("Mixed");
    expect(laborStateLabel("INSUFFICIENT_DATA")).toBe("Insufficient data");
  });
});

describe("employmentStateTone -- same no-directional-color principle", () => {
  it("never maps INSUFFICIENT_DATA to a directional tone", () => {
    expect(employmentStateTone("INSUFFICIENT_DATA")).toBe("unavailable");
  });

  it.each(["EXPANDING", "COOLING", "STABLE", "CONTRACTING", "RECOVERING"] as const)(
    "gives %s the same neutral tone",
    (state) => {
      expect(employmentStateTone(state)).toBe("neutral");
    },
  );
});

describe("employmentStateLabel", () => {
  it("renders every EmploymentState with a readable label", () => {
    expect(employmentStateLabel("EXPANDING")).toBe("Expanding");
    expect(employmentStateLabel("RECOVERING")).toBe("Recovering");
  });
});

describe("employmentConditionLabel / employmentMomentumLabel", () => {
  it("renders every EmploymentCondition value", () => {
    expect(employmentConditionLabel("EXPANDING")).toBe("Expanding");
    expect(employmentConditionLabel("FLAT")).toBe("Flat");
    expect(employmentConditionLabel("CONTRACTING")).toBe("Contracting");
  });

  it("renders every EmploymentMomentum value -- IMPROVING/STEADY/WORSENING, never ACCELERATING/DECELERATING", () => {
    expect(employmentMomentumLabel("IMPROVING")).toBe("Improving");
    expect(employmentMomentumLabel("STEADY")).toBe("Steady");
    expect(employmentMomentumLabel("WORSENING")).toBe("Worsening");
  });
});

describe("unemploymentStateTone / unemploymentStateLabel", () => {
  it("never maps INSUFFICIENT_DATA to a directional tone", () => {
    expect(unemploymentStateTone("INSUFFICIENT_DATA")).toBe("unavailable");
  });

  it("renders DETERIORATING with a readable label, title-cased correctly", () => {
    expect(unemploymentStateLabel("DETERIORATING")).toBe("Deteriorating");
  });
});

describe("...LabelOrRaw fallback functions", () => {
  it("looks up a recognized value and falls back to the raw string otherwise", () => {
    expect(laborStateLabelOrRaw("STRENGTHENING")).toBe("Strengthening");
    expect(laborStateLabelOrRaw("SOMETHING_NEW")).toBe("SOMETHING_NEW");

    expect(employmentStateLabelOrRaw("RECOVERING")).toBe("Recovering");
    expect(employmentStateLabelOrRaw("SOMETHING_NEW")).toBe("SOMETHING_NEW");

    expect(employmentConditionLabelOrRaw("FLAT")).toBe("Flat");
    expect(employmentConditionLabelOrRaw("SOMETHING_NEW")).toBe("SOMETHING_NEW");

    expect(employmentMomentumLabelOrRaw("WORSENING")).toBe("Worsening");
    expect(employmentMomentumLabelOrRaw("SOMETHING_NEW")).toBe("SOMETHING_NEW");

    expect(unemploymentStateLabelOrRaw("DETERIORATING")).toBe("Deteriorating");
    expect(unemploymentStateLabelOrRaw("SOMETHING_NEW")).toBe("SOMETHING_NEW");
  });
});

describe("laborChangeComponentLabelOrRaw", () => {
  it("renders all three Labor components", () => {
    expect(laborChangeComponentLabelOrRaw("LABOR")).toBe("Labor");
    expect(laborChangeComponentLabelOrRaw("EMPLOYMENT")).toBe("Employment");
    expect(laborChangeComponentLabelOrRaw("UNEMPLOYMENT")).toBe("Unemployment");
  });

  it("falls back to the raw string for an unrecognized (e.g. Inflation) component", () => {
    expect(laborChangeComponentLabelOrRaw("PRIMARY_MOMENTUM")).toBe("PRIMARY_MOMENTUM");
  });
});

describe("laborChangeFieldLabel", () => {
  it("labels every Employment/Unemployment numeric field", () => {
    expect(laborChangeFieldLabel("current_3m_avg_jobs")).toBe("Current 3M avg");
    expect(laborChangeFieldLabel("momentum_delta_jobs")).toBe("Momentum delta");
    expect(laborChangeFieldLabel("delta_pp")).toBe("Delta");
  });

  it("falls back to the raw field name for an unrecognized field", () => {
    expect(laborChangeFieldLabel("something_new")).toBe("something_new");
  });
});

describe("isJobCountField / isPercentagePointDeltaField -- the PAYEMS unit distinction (§15/§16)", () => {
  it("classifies Employment's own three numeric fields as job-count fields", () => {
    expect(isJobCountField("current_3m_avg_jobs")).toBe(true);
    expect(isJobCountField("prior_3m_avg_jobs")).toBe(true);
    expect(isJobCountField("momentum_delta_jobs")).toBe(true);
  });

  it("never classifies Unemployment's own numeric fields as job-count fields", () => {
    expect(isJobCountField("current_3m_avg")).toBe(false);
    expect(isJobCountField("prior_year_3m_avg")).toBe(false);
    expect(isJobCountField("delta_pp")).toBe(false);
  });

  it("classifies only delta_pp as a percentage-point delta field", () => {
    expect(isPercentagePointDeltaField("delta_pp")).toBe(true);
    expect(isPercentagePointDeltaField("current_3m_avg_jobs")).toBe(false);
    expect(isPercentagePointDeltaField("current_3m_avg")).toBe(false);
  });
});
