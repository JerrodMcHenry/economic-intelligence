/**
 * Component-level tests for Increment #19C's "Latest Data Detected"
 * section. Renders `LatestDataDetected` directly with an `items` prop
 * -- no mocked network layer needed (this component never fetches;
 * see its own docstring) -- the same discipline this project already
 * uses for other pure presentation components.
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  buildDetectedAnalysisChange,
  buildDetectedObservationChange,
  buildLatestCheck,
  buildReleaseProcessingStatusItem,
} from "../../test/fixtures/processingStatus";
import { LatestDataDetected } from "./LatestDataDetected";

describe("empty state", () => {
  it("shows a precise, non-inventive empty message when zero items are returned", () => {
    render(<LatestDataDetected items={[]} />);
    expect(screen.getByText("No tracked release processing records are available yet.")).toBeInTheDocument();
    expect(screen.queryByText(/no economic data/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/no releases/i)).not.toBeInTheDocument();
  });
});

describe("NOT_CHECKED", () => {
  it("renders restrained, non-alarming copy for a never-checked occurrence", () => {
    const item = buildReleaseProcessingStatusItem({ latest_check: buildLatestCheck({ status: "NOT_CHECKED", checked_at: null }) });
    render(<LatestDataDetected items={[item]} />);
    expect(screen.getByText("Not yet checked by Economic Intelligence.")).toBeInTheDocument();
    expect(screen.queryByText(/never checked/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/failure|failed/i)).not.toBeInTheDocument();
  });

  it("REGRESSION (caught via live visual review): shows neither 'Source data changes' nor a dangling 'Tracked analysis changes' heading when there is no evidence of either kind", () => {
    const item = buildReleaseProcessingStatusItem({
      latest_check: buildLatestCheck({ status: "NOT_CHECKED", checked_at: null }),
      detected_observation_changes: [],
      detected_analysis_changes: [],
    });
    render(<LatestDataDetected items={[item]} />);
    expect(screen.queryByText("Source data changes")).not.toBeInTheDocument();
    expect(screen.queryByText("Tracked analysis changes")).not.toBeInTheDocument();
  });
});

describe("NO_CHANGE", () => {
  it("is quiet: no giant success card, no change lists when there is no history", () => {
    const item = buildReleaseProcessingStatusItem({ latest_check: buildLatestCheck({ status: "NO_CHANGE" }) });
    render(<LatestDataDetected items={[item]} />);
    expect(screen.getByText("No new data detected in the latest check.")).toBeInTheDocument();
    expect(screen.queryByText("Source data changes")).not.toBeInTheDocument();
    expect(screen.queryByText(/earlier changes were detected/i)).not.toBeInTheDocument();
  });

  it("THE CONTRADICTORY-EVIDENCE TEST: NO_CHANGE stays the primary message even when historical evidence exists", () => {
    const item = buildReleaseProcessingStatusItem({
      latest_check: buildLatestCheck({ status: "NO_CHANGE" }),
      detected_observation_changes: [buildDetectedObservationChange()],
      detected_analysis_changes: [buildDetectedAnalysisChange()],
    });
    render(<LatestDataDetected items={[item]} />);

    expect(screen.getByText("No new data detected in the latest check.")).toBeInTheDocument();
    // Must NOT switch to the CHANGES_DETECTED message.
    expect(screen.queryByText("Data changes detected.")).not.toBeInTheDocument();
    // The earlier evidence is still shown, explicitly framed as earlier.
    expect(screen.getByText(/earlier changes were detected for this release occurrence/i)).toBeInTheDocument();
    expect(screen.getByText("Source data changes")).toBeInTheDocument();
  });
});

describe("CHANGES_DETECTED", () => {
  it("shows release name, scheduled date, status, checked timestamp, and detected changes", () => {
    const item = buildReleaseProcessingStatusItem({
      latest_check: buildLatestCheck({ status: "CHANGES_DETECTED", checked_at: "2026-09-13T21:42:00+00:00" }),
      detected_observation_changes: [buildDetectedObservationChange()],
    });
    render(<LatestDataDetected items={[item]} />);

    expect(screen.getByText("Personal Income and Outlays")).toBeInTheDocument();
    expect(screen.getByText("Data changes detected.")).toBeInTheDocument();
    expect(screen.getByText(/^Checked/)).toBeInTheDocument();
    expect(screen.getByText("Core PCE Price Index")).toBeInTheDocument();
    // Not framed as "earlier" -- this IS the latest check's own evidence set.
    expect(screen.queryByText(/earlier changes were detected/i)).not.toBeInTheDocument();
  });

  it("NEW vs REVISED copy, and previous → new value formatting", () => {
    const newChange = buildDetectedObservationChange({
      series_id: "UNRATE",
      series_title: "Unemployment Rate",
      units: "Percent",
      change_type: "NEW",
      previous_value: null,
      new_value: 3.9,
    });
    const item = buildReleaseProcessingStatusItem({
      latest_check: buildLatestCheck({ status: "CHANGES_DETECTED" }),
      detected_observation_changes: [newChange],
    });
    render(<LatestDataDetected items={[item]} />);

    expect(screen.getByText(/New observation/)).toBeInTheDocument();
    expect(screen.getByText("3.9%")).toBeInTheDocument();
    expect(screen.queryByText(/→/)).not.toBeInTheDocument(); // no arrow for NEW
  });

  it("REVISED shows previous → new", () => {
    const item = buildReleaseProcessingStatusItem({
      latest_check: buildLatestCheck({ status: "CHANGES_DETECTED" }),
      detected_observation_changes: [buildDetectedObservationChange({ change_type: "REVISED", previous_value: 120.0, new_value: 121.5, units: "Index 2017=100" })],
    });
    render(<LatestDataDetected items={[item]} />);

    expect(screen.getByText(/Revision detected/)).toBeInTheDocument();
    expect(screen.queryByText("120%")).not.toBeInTheDocument(); // sanity: never appends % to an index value
    expect(screen.getByText(/120/)).toBeInTheDocument();
    expect(screen.getByText(/121.5/)).toBeInTheDocument();
  });

  it("THE ORDER/TRUNCATION TEST: shows the first 3 observation changes, in backend order, never reordered", () => {
    const changes = [
      buildDetectedObservationChange({ series_id: "A", series_title: "Series A" }),
      buildDetectedObservationChange({ series_id: "B", series_title: "Series B" }),
      buildDetectedObservationChange({ series_id: "C", series_title: "Series C" }),
      buildDetectedObservationChange({ series_id: "D", series_title: "Series D" }),
    ];
    const item = buildReleaseProcessingStatusItem({
      latest_check: buildLatestCheck({ status: "CHANGES_DETECTED" }),
      detected_observation_changes: changes,
    });
    render(<LatestDataDetected items={[item]} />);

    const section = screen.getByText("Source data changes").closest("div") as HTMLElement;
    const items = within(section).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]!.textContent).toMatch(/Series A/);
    expect(items[1]!.textContent).toMatch(/Series B/);
    expect(items[2]!.textContent).toMatch(/Series C/);
    expect(screen.queryByText("Series D")).not.toBeInTheDocument();
  });

  it("observation change without any analysis change is a valid, non-alarming result", () => {
    const item = buildReleaseProcessingStatusItem({
      latest_check: buildLatestCheck({ status: "CHANGES_DETECTED" }),
      detected_observation_changes: [buildDetectedObservationChange()],
      detected_analysis_changes: [],
    });
    render(<LatestDataDetected items={[item]} />);

    expect(screen.getByText("No tracked evidence changed during this processing history.")).toBeInTheDocument();
    expect(screen.queryByText(/no economic impact/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/nothing changed/i)).not.toBeInTheDocument();
  });

  it("renders a metric-changed analysis event with component/event/field labels and evaluation period", () => {
    const item = buildReleaseProcessingStatusItem({
      latest_check: buildLatestCheck({ status: "CHANGES_DETECTED" }),
      detected_analysis_changes: [buildDetectedAnalysisChange({ component: "TARGET", event_type: "METRIC_CHANGED", field: "target_gap_pp" })],
    });
    render(<LatestDataDetected items={[item]} />);

    expect(screen.getByText(/Target/)).toBeInTheDocument();
    expect(screen.getByText(/Metric changed/)).toBeInTheDocument();
    expect(screen.getByText(/Target gap/)).toBeInTheDocument();
  });

  it("renders a state-changed analysis event through the canonical state label, not the raw enum string", () => {
    const item = buildReleaseProcessingStatusItem({
      latest_check: buildLatestCheck({ status: "CHANGES_DETECTED" }),
      detected_analysis_changes: [
        buildDetectedAnalysisChange({ component: "PRIMARY_MOMENTUM", event_type: "STATE_CHANGED", field: "state", previous_value: "COOLING", current_value: "MIXED" }),
      ],
    });
    render(<LatestDataDetected items={[item]} />);

    expect(screen.getByText(/Cooling/)).toBeInTheDocument();
    expect(screen.getByText(/Mixed/)).toBeInTheDocument();
  });

  it("THE ORDER/TRUNCATION TEST (analysis): shows the first 3 analysis changes, in backend order", () => {
    const changes = [
      buildDetectedAnalysisChange({ field: "r_1m_annualized" }),
      buildDetectedAnalysisChange({ field: "r_3m_annualized" }),
      buildDetectedAnalysisChange({ field: "r_6m_annualized" }),
      buildDetectedAnalysisChange({ field: "r_12m" }),
    ];
    const item = buildReleaseProcessingStatusItem({
      latest_check: buildLatestCheck({ status: "CHANGES_DETECTED" }),
      detected_analysis_changes: changes,
    });
    render(<LatestDataDetected items={[item]} />);

    const section = screen.getByText("Tracked analysis changes").closest("div") as HTMLElement;
    const items = within(section).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]!.textContent).toMatch(/1M annualized/);
    expect(items[1]!.textContent).toMatch(/3M annualized/);
    expect(items[2]!.textContent).toMatch(/6M annualized/);
    expect(screen.queryByText(/12M/)).not.toBeInTheDocument();
  });
});

describe("THE NO-CAUSAL-NESTING TEST", () => {
  it("renders Source data changes and Tracked analysis changes as separate sibling groups, with no causal language anywhere", () => {
    const item = buildReleaseProcessingStatusItem({
      latest_check: buildLatestCheck({ status: "CHANGES_DETECTED" }),
      detected_observation_changes: [buildDetectedObservationChange(), buildDetectedObservationChange({ series_id: "PCEPI", series_title: "PCE Price Index" })],
      detected_analysis_changes: [buildDetectedAnalysisChange(), buildDetectedAnalysisChange({ field: "r_6m_annualized" })],
    });
    const { container } = render(<LatestDataDetected items={[item]} />);

    const sourceHeading = screen.getByText("Source data changes");
    const analysisHeading = screen.getByText("Tracked analysis changes");
    // Two distinct headings, and analysis items never nested inside an
    // observation <li>, or vice versa.
    expect(sourceHeading).not.toBe(analysisHeading);
    const sourceGroup = sourceHeading.closest("div") as HTMLElement;
    expect(within(sourceGroup).queryByText("Tracked analysis changes")).not.toBeInTheDocument();

    const bodyText = container.textContent ?? "";
    for (const forbidden of [/\bcaused\b/i, /\bbecause of\b/i, /impact of this revision/i, /resulting analysis change/i]) {
      expect(bodyText).not.toMatch(forbidden);
    }
  });
});

describe("PARTIAL_CHECK", () => {
  it("clearly communicates incompleteness while still showing real detected evidence", () => {
    const item = buildReleaseProcessingStatusItem({
      latest_check: buildLatestCheck({ status: "PARTIAL_CHECK" }),
      detected_observation_changes: [buildDetectedObservationChange()],
    });
    render(<LatestDataDetected items={[item]} />);

    expect(screen.getByText("Check incomplete.")).toBeInTheDocument();
    expect(screen.getByText("Some associated series could not be checked.")).toBeInTheDocument();
    expect(screen.getByText("Core PCE Price Index")).toBeInTheDocument();
    expect(screen.queryByText(/partial data published/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/release partially available/i)).not.toBeInTheDocument();
  });
});

describe("CHECK_FAILED", () => {
  it("stays local and non-catastrophic, never leaking internal error detail", () => {
    const item = buildReleaseProcessingStatusItem({ latest_check: buildLatestCheck({ status: "CHECK_FAILED" }) });
    render(<LatestDataDetected items={[item]} />);

    expect(screen.getByText("Check unsuccessful.")).toBeInTheDocument();
    expect(screen.getByText("Economic Intelligence could not complete the latest provider check.")).toBeInTheDocument();
    const bodyText = document.body.textContent ?? "";
    expect(bodyText).not.toMatch(/exception|stack trace|traceback|FREDAuthError|FREDTimeoutError/i);
  });

  it("frames pre-existing evidence as earlier when the latest check itself failed", () => {
    const item = buildReleaseProcessingStatusItem({
      latest_check: buildLatestCheck({ status: "CHECK_FAILED" }),
      detected_observation_changes: [buildDetectedObservationChange()],
    });
    render(<LatestDataDetected items={[item]} />);
    expect(screen.getByText(/earlier changes were detected for this release occurrence/i)).toBeInTheDocument();
  });
});

describe("date rendering", () => {
  it("renders scheduled_date/observation_date/evaluation_period as date-only, without a timezone rollback", () => {
    const item = buildReleaseProcessingStatusItem({
      scheduled_date: "2026-01-01",
      latest_check: buildLatestCheck({ status: "CHANGES_DETECTED" }),
      detected_observation_changes: [buildDetectedObservationChange({ observation_date: "2026-01-01" })],
    });
    render(<LatestDataDetected items={[item]} />);
    // "January 1, 2026" would regress to "December 31, 2025" if ever
    // routed through `new Date("2026-01-01")` in a timezone behind UTC.
    expect(screen.getAllByText(/January 1, 2026/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/December 31, 2025/)).not.toBeInTheDocument();
  });
});

describe("methodology/data basis disclosure", () => {
  it("exposes methodology_id and data_basis behind a details disclosure, not inline", () => {
    const item = buildReleaseProcessingStatusItem({
      latest_check: buildLatestCheck({ status: "CHANGES_DETECTED" }),
      detected_analysis_changes: [buildDetectedAnalysisChange({ methodology_id: "inflation_v1.0", data_basis: "revised" })],
    });
    render(<LatestDataDetected items={[item]} />);
    expect(screen.getByText("inflation_v1.0")).toBeInTheDocument();
    expect(screen.getByText("revised")).toBeInTheDocument();
  });
});
