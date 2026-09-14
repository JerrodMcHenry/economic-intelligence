/**
 * Tests for the one result-explanation component (Increment #17C):
 * "Why is momentum {State}?" combines the backend's own already-
 * classified `state` with the backend evidence already present on the
 * response. The most important test in this file is the contradictory-
 * evidence test below -- it proves the frontend displays exactly what
 * the backend classified even when the numbers, read by a human, might
 * suggest a different state. No `if (r3m < ...)` logic exists in
 * WhyThisState.tsx or anywhere in its import graph (see
 * src/test/no-economic-logic.test.ts and
 * src/test/no-explanation-classification-logic.test.ts for the
 * architectural guards backing that claim).
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { buildMomentum } from "../../test/fixtures/inflation";
import { WhyThisState } from "./WhyThisState";

async function openPanel() {
  const user = userEvent.setup();
  await user.click(screen.getByText(/^Why [A-Za-z ]+\?$/));
}

describe("WhyThisState", () => {
  it("renders a 'Why {State}?' trigger naming the backend's own state", () => {
    render(<WhyThisState momentum={buildMomentum({ state: "COOLING" })} />);
    expect(screen.getByText("Why Cooling?")).toBeInTheDocument();
  });

  it.each(["COOLING", "HEATING", "STABLE", "MIXED", "INSUFFICIENT_DATA"] as const)(
    "opens to show the curated explanation for %s",
    async (state) => {
      render(<WhyThisState momentum={buildMomentum({ state })} />);
      await openPanel();

      const expectedLabel = state === "INSUFFICIENT_DATA" ? "Insufficient data" : state[0] + state.slice(1).toLowerCase();
      expect(screen.getByText(`Why ${expectedLabel}?`)).toBeInTheDocument();
    },
  );

  it("shows the backend's own 3M/6M/12M evidence values, not recalculated ones", async () => {
    render(
      <WhyThisState
        momentum={buildMomentum({ state: "STABLE", r_3m_annualized: 2.345, r_6m_annualized: 2.456, r_12m: 2.5 })}
      />,
    );
    await openPanel();

    expect(screen.getByText("2.35%")).toBeInTheDocument();
    expect(screen.getByText("2.46%")).toBeInTheDocument();
    expect(screen.getByText("2.50%")).toBeInTheDocument();
  });

  it("shows the backend's own neutral band boundaries when present", async () => {
    render(<WhyThisState momentum={buildMomentum({ state: "STABLE", lower_boundary: 2.4, upper_boundary: 2.6 })} />);
    await openPanel();

    expect(screen.getByText(/2\.40% – 2\.60%/)).toBeInTheDocument();
  });

  it("omits the neutral band row when the backend didn't provide boundaries (e.g. INSUFFICIENT_DATA)", async () => {
    render(
      <WhyThisState
        momentum={buildMomentum({ state: "INSUFFICIENT_DATA", lower_boundary: null, upper_boundary: null })}
      />,
    );
    await openPanel();

    expect(screen.queryByText("Neutral band")).not.toBeInTheDocument();
  });

  it("THE CONTRADICTORY-EVIDENCE TEST: displays MIXED even when the raw numbers, read by a human, would suggest STABLE", async () => {
    // r_3m and r_6m both sit comfortably inside a band that would look
    // "stable" to a human doing quick mental math against r_12m -- but
    // the backend is the sole source of the classification, and it
    // says MIXED. WhyThisState must render exactly what the backend
    // said, never recompute or second-guess it from the numbers.
    const contradictoryMomentum = buildMomentum({
      state: "MIXED",
      r_3m_annualized: 2.5,
      r_6m_annualized: 2.5,
      r_12m: 2.5,
      lower_boundary: 2.4,
      upper_boundary: 2.6,
      neutral_band_pp: 0.1,
    });

    render(<WhyThisState momentum={contradictoryMomentum} />);

    expect(screen.getByText("Why Mixed?")).toBeInTheDocument();
    expect(screen.queryByText("Why Stable?")).not.toBeInTheDocument();

    await openPanel();
    expect(
      screen.getByText(
        "The 3-month and 6-month annualized rates aren't consistently above, below, or within the neutral band together, so the result doesn't meet the requirements for cooling, heating, or stable.",
      ),
    ).toBeInTheDocument();
  });

  it("THE CONTRADICTORY-EVIDENCE TEST (mirror case): displays STABLE even when 3M looks like it could read HEATING", async () => {
    // The inverse: state says STABLE while r_3m alone is well above
    // r_12m -- a human skimming only r_3m vs. r_12m might expect
    // "heating." WhyThisState must still say STABLE, because that is
    // what the backend classified (evaluating r_3m and r_6m together,
    // which this component never does).
    const contradictoryMomentum = buildMomentum({
      state: "STABLE",
      r_3m_annualized: 4.9,
      r_6m_annualized: 2.5,
      r_12m: 2.5,
      lower_boundary: 2.4,
      upper_boundary: 2.6,
    });

    render(<WhyThisState momentum={contradictoryMomentum} />);

    expect(screen.getByText("Why Stable?")).toBeInTheDocument();
    expect(screen.queryByText("Why Heating?")).not.toBeInTheDocument();
  });

  it("never renders explanation.title as a heading (avoided deliberately to prevent duplicating the state Badge's own text)", async () => {
    render(<WhyThisState momentum={buildMomentum({ state: "COOLING" })} />);
    await openPanel();

    // "Cooling" is the Badge's own label elsewhere on the page; the
    // panel here should present its content without repeating that
    // exact word as its own heading a second time.
    const panelHeadings = screen.queryAllByRole("heading", { name: "Cooling" });
    expect(panelHeadings).toHaveLength(0);
  });
});
