import { describe, expect, it } from "vitest";

import {
  confirmationRelationshipLabel,
  confirmationRelationshipLabelOrRaw,
  confirmationRelationshipTone,
  inflationStateLabel,
  inflationStateLabelOrRaw,
  inflationStateTone,
} from "./inflationLabels";

describe("inflationStateTone", () => {
  it("never maps INSUFFICIENT_DATA to a directional tone -- it must read as unavailable evidence, not a direction", () => {
    expect(inflationStateTone("INSUFFICIENT_DATA")).toBe("unavailable");
  });

  it.each([
    ["COOLING", "cool"],
    ["STABLE", "neutral"],
    ["HEATING", "warm"],
    ["MIXED", "caution"],
  ] as const)("maps %s to the %s tone", (state, tone) => {
    expect(inflationStateTone(state)).toBe(tone);
  });
});

describe("inflationStateLabel", () => {
  it("renders a readable label distinct from the raw enum casing", () => {
    expect(inflationStateLabel("INSUFFICIENT_DATA")).toBe("Insufficient data");
    expect(inflationStateLabel("COOLING")).toBe("Cooling");
  });
});

describe("confirmationRelationshipTone", () => {
  it("maps UNAVAILABLE to the same muted 'unavailable' tone used for insufficient data", () => {
    expect(confirmationRelationshipTone("UNAVAILABLE")).toBe("unavailable");
  });

  it("gives DIVERGES a caution tone", () => {
    expect(confirmationRelationshipTone("DIVERGES")).toBe("caution");
  });
});

describe("inflationStateLabelOrRaw / confirmationRelationshipLabelOrRaw", () => {
  it("looks up a recognized state value from a ChangeEvent", () => {
    expect(inflationStateLabelOrRaw("HEATING")).toBe("Heating");
  });

  it("falls back to the raw string for an unrecognized value rather than guessing", () => {
    expect(inflationStateLabelOrRaw("SOMETHING_NEW")).toBe("SOMETHING_NEW");
  });

  it("looks up a recognized relationship value from a ChangeEvent", () => {
    expect(confirmationRelationshipLabelOrRaw("DIVERGES")).toBe("Diverges");
  });

  it("falls back to the raw string for an unrecognized relationship value", () => {
    expect(confirmationRelationshipLabelOrRaw("SOMETHING_NEW")).toBe("SOMETHING_NEW");
  });
});

describe("confirmationRelationshipLabel", () => {
  it("renders every relationship with a readable label", () => {
    expect(confirmationRelationshipLabel("CONFIRMS")).toBe("Confirms");
    expect(confirmationRelationshipLabel("INCONCLUSIVE")).toBe("Inconclusive");
  });
});
