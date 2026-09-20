/**
 * Behavioral tests for the Intelligence History experience
 * (Increment #32).
 *
 * The bar these enforce is not "it renders". It is that the experience
 * stays HONEST: that what MacroChipz knew then is never blurred into
 * what today's data says, that a replay mismatch is visible as an
 * integrity problem, that reconstructed inputs are disclosed, and that
 * nothing on screen claims a cause the backend did not record.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/errors";
import { getMonitorHistoryDetail } from "../../api/monitorHistory";
import type { MonitorHistoryResponse } from "../../api/monitorHistory.types";
import type { ApiResourceState } from "../../api/useApiResource";
import { inflationStateLabelOrRaw, inflationStateToneOrNeutral } from "../../lib/inflationLabels";
import * as copy from "../../lib/historyCopy";
import {
  buildEmptyHistoryResponse,
  buildHistoryDetail,
  buildHistoryResponse,
  buildMethodologyDifferenceDetail,
  buildMismatchDetail,
  buildNotReplayableDetail,
  buildRecordedEntry,
  buildReplaySummary,
  buildRevisedDetail,
} from "../../test/fixtures/monitorHistory";
import { IntelligenceHistorySection } from "./IntelligenceHistorySection";

vi.mock("../../api/monitorHistory", async () => {
  const actual = await vi.importActual<typeof import("../../api/monitorHistory")>("../../api/monitorHistory");
  return { ...actual, getMonitorHistoryDetail: vi.fn() };
});

const mockedGetDetail = vi.mocked(getMonitorHistoryDetail);

beforeEach(() => {
  mockedGetDetail.mockReset();
  mockedGetDetail.mockResolvedValue(buildHistoryDetail());
});

function renderSection(state: ApiResourceState<MonitorHistoryResponse>) {
  return render(
    <IntelligenceHistorySection
      monitor="inflation"
      history={{ ...state, reload: vi.fn() }}
      headingId="test-history-heading"
      stateLabel={inflationStateLabelOrRaw}
      stateTone={inflationStateToneOrNeutral}
    />,
  );
}

async function openFirstEntry() {
  await userEvent.click(screen.getAllByText("July 2026")[0] as HTMLElement);
}

describe("resource states", () => {
  it("shows a labelled skeleton and no fabricated values while loading", () => {
    renderSection({ status: "loading" });

    expect(screen.getByRole("status", { name: copy.LOADING_LABEL })).toBeInTheDocument();
    expect(screen.queryByText("Cooling")).not.toBeInTheDocument();
  });

  it("shows a truthful error with a retry action, never a status code", () => {
    renderSection({ status: "error", error: new ApiError("http", "Request failed with status 503.", 503) });

    expect(screen.getByRole("alert")).toHaveTextContent(copy.ERROR_MESSAGE);
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.queryByText(/503/)).not.toBeInTheDocument();
  });

  it("explains an empty history rather than rendering a bare blank space", () => {
    renderSection({ status: "success", data: buildEmptyHistoryResponse() });

    expect(screen.getByText(copy.EMPTY_HISTORY_COPY)).toBeInTheDocument();
    expect(screen.queryByRole("listitem")).not.toBeInTheDocument();
  });
});

describe("the history list", () => {
  it("renders one entry per recorded result with its period, state and replay status", () => {
    renderSection({
      status: "success",
      data: buildHistoryResponse({
        entries: [
          buildRecordedEntry({ recorded_result_id: 2, state: "COOLING", evaluation_period: "2026-07-01" }),
          buildRecordedEntry({ recorded_result_id: 1, state: "HEATING", evaluation_period: "2026-06-01" }),
        ],
      }),
    });

    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("July 2026")).toBeInTheDocument();
    expect(screen.getByText("June 2026")).toBeInTheDocument();
    expect(screen.getAllByText("Replay verified")).toHaveLength(2);
  });

  it("always shows the revision disclosure alongside real history", () => {
    renderSection({ status: "success", data: buildHistoryResponse() });
    expect(screen.getByText(copy.REVISION_DISCLOSURE)).toBeInTheDocument();
  });

  it("distinguishes a changed conclusion about the same month from a new month", () => {
    renderSection({
      status: "success",
      data: buildHistoryResponse({
        entries: [
          buildRecordedEntry({
            state: "COOLING",
            previous: {
              recorded_result_id: 1,
              state: "HEATING",
              evaluation_period: "2026-07-01",
              calculated_at: "2026-07-20T10:00:00+00:00",
              same_evaluation_period: true,
              state_changed: true,
            },
          }),
        ],
      }),
    });

    expect(screen.getByText(/Revised conclusion for the same period; previously Heating\./)).toBeInTheDocument();
  });
});

describe("replay status is reported honestly", () => {
  it("marks a verified replay with the success feedback treatment, not an economic-state colour", () => {
    renderSection({ status: "success", data: buildHistoryResponse() });

    const badge = screen.getByText("Replay verified").closest("span");
    expect(badge?.className).toMatch(/feedback-success/);
    expect(badge?.className).not.toMatch(/state-(cool|warm|neutral|caution)/);
  });

  it("surfaces a mismatch as an integrity problem rather than smoothing it away", async () => {
    mockedGetDetail.mockResolvedValue(buildMismatchDetail());
    renderSection({
      status: "success",
      data: buildHistoryResponse({
        entries: [
          buildRecordedEntry({
            state: "COOLING",
            replay: buildReplaySummary({ outcome: "MISMATCH", replayed_state: "HEATING" }),
          }),
        ],
      }),
    });

    const badge = screen.getByText("Replay mismatch").closest("span");
    expect(badge?.className).toMatch(/feedback-error/);

    await openFirstEntry();
    expect(
      await screen.findByText(/Recalculating from the data available then produces Heating, not Cooling\./),
    ).toBeInTheDocument();
  });

  it("explains why a result cannot be verified instead of implying it was", async () => {
    mockedGetDetail.mockResolvedValue(buildNotReplayableDetail());
    renderSection({
      status: "success",
      data: buildHistoryResponse({
        entries: [
          buildRecordedEntry({
            replay: buildReplaySummary({
              outcome: "NOT_REPLAYABLE",
              replayed_state: null,
              reason: "VERSION_HISTORY_STARTS_AFTER_CALCULATION",
            }),
          }),
        ],
      }),
    });

    expect(screen.getByText("Cannot verify")).toBeInTheDocument();
    await openFirstEntry();
    expect(
      await screen.findByText(/only began tracking this data after the result was calculated/i),
    ).toBeInTheDocument();
  });

  it("describes every replay outcome in text, so colour is never the only carrier", () => {
    renderSection({
      status: "success",
      data: buildHistoryResponse({
        entries: [
          buildRecordedEntry({ recorded_result_id: 3, replay: buildReplaySummary({ outcome: "MATCH" }) }),
          buildRecordedEntry({ recorded_result_id: 2, replay: buildReplaySummary({ outcome: "MISMATCH" }) }),
          buildRecordedEntry({ recorded_result_id: 1, replay: buildReplaySummary({ outcome: "NOT_REPLAYABLE" }) }),
        ],
      }),
    });

    for (const label of ["Replay verified", "Replay mismatch", "Cannot verify"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });
});

describe("backfill disclosure", () => {
  it("flags reconstructed inputs on the row and explains them in the detail", async () => {
    mockedGetDetail.mockResolvedValue(
      buildHistoryDetail({
        recorded: buildRecordedEntry({ replay: buildReplaySummary({ inputs_include_backfilled: true }) }),
      }),
    );
    renderSection({
      status: "success",
      data: buildHistoryResponse({
        entries: [buildRecordedEntry({ replay: buildReplaySummary({ inputs_include_backfilled: true }) })],
      }),
    });

    expect(screen.getByText(copy.BACKFILL_BADGE_LABEL)).toBeInTheDocument();

    await openFirstEntry();
    expect(await screen.findByText(copy.BACKFILL_DISCLOSURE)).toBeInTheDocument();
  });

  it("says nothing about reconstruction when every input was observed", async () => {
    renderSection({ status: "success", data: buildHistoryResponse() });

    expect(screen.queryByText(copy.BACKFILL_BADGE_LABEL)).not.toBeInTheDocument();
    await openFirstEntry();
    await screen.findByText(copy.THEN_HEADING);
    expect(screen.queryByText(copy.BACKFILL_DISCLOSURE)).not.toBeInTheDocument();
  });
});

describe("then vs today", () => {
  it("does not request detail until an entry is opened", () => {
    renderSection({ status: "success", data: buildHistoryResponse() });
    expect(mockedGetDetail).not.toHaveBeenCalled();
  });

  it("keeps the two views under permanently distinct headings", async () => {
    renderSection({ status: "success", data: buildHistoryResponse() });
    await openFirstEntry();

    expect(await screen.findByText(copy.THEN_HEADING)).toBeInTheDocument();
    expect(screen.getByText(copy.TODAY_HEADING)).toBeInTheDocument();
  });

  it("states plainly when today's data still produces the same conclusion", async () => {
    renderSection({ status: "success", data: buildHistoryResponse() });
    await openFirstEntry();

    expect(await screen.findByText(/Today's revised data still produces Cooling for this period\./)).toBeInTheDocument();
    expect(screen.getByText(/None of the values this result used have changed since\./)).toBeInTheDocument();
  });

  it("shows a revision as a then-and-today pair with the backend's own classification", async () => {
    mockedGetDetail.mockResolvedValue(buildRevisedDetail());
    renderSection({ status: "success", data: buildHistoryResponse() });
    await openFirstEntry();

    const table = await screen.findByRole("table");
    const revisedRow = within(table).getByText("Revised").closest("tr") as HTMLElement;
    expect(within(revisedRow).getByText("130.658")).toBeInTheDocument();
    expect(within(revisedRow).getByText("131.204")).toBeInTheDocument();
    expect(
      screen.getByText(/Using today's revised data, the same period would now be classified Heating\./),
    ).toBeInTheDocument();
  });

  it("refuses to compare across methodology versions rather than faking a result", async () => {
    mockedGetDetail.mockResolvedValue(buildMethodologyDifferenceDetail());
    renderSection({ status: "success", data: buildHistoryResponse() });
    await openFirstEntry();

    expect(await screen.findByText(/Re-running today's methodology would answer a different question/)).toBeInTheDocument();
    expect(screen.getByText(/Recorded under inflation_v0\.9/)).toBeInTheDocument();
    expect(screen.queryByText(/would now be classified/)).not.toBeInTheDocument();
  });

  it("shows a per-entry error without blanking the rest of the list", async () => {
    mockedGetDetail.mockRejectedValue(new ApiError("http", "Request failed with status 500.", 500));
    renderSection({
      status: "success",
      data: buildHistoryResponse({
        entries: [buildRecordedEntry({ recorded_result_id: 2 }), buildRecordedEntry({ recorded_result_id: 1 })],
      }),
    });
    await openFirstEntry();

    expect(await screen.findByText(copy.DETAIL_ERROR_MESSAGE)).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });
});

describe("related changes never become a causal claim", () => {
  it("frames same-run changes as co-occurring, not causing", async () => {
    renderSection({ status: "success", data: buildHistoryResponse() });
    await openFirstEntry();

    expect(await screen.findByText(copy.RELATED_CHANGES_NOTE)).toBeInTheDocument();

    // The disclaimer itself necessarily contains the word "caused"
    // ("does not record that one caused the other"), so it is removed
    // before matching -- the check is for an AFFIRMATIVE causal claim
    // anywhere ELSE on screen, not for the substring.
    const rendered = (document.body.textContent ?? "").replace(copy.RELATED_CHANGES_NOTE, "");
    for (const claim of [
      /\bcaused (?:this|the|it)\b/i,
      /\bthis caused\b/i,
      /\bled to\b/i,
      /\bresulted in\b/i,
      /\bbecause of (?:this|these)\b/i,
      /\btriggered\b/i,
    ]) {
      expect(rendered).not.toMatch(claim);
    }
  });

  it("counts same-run changes the result did not use rather than hiding them", async () => {
    mockedGetDetail.mockResolvedValue(buildHistoryDetail({ other_changes_in_same_run: 113 }));
    renderSection({ status: "success", data: buildHistoryResponse() });
    await openFirstEntry();

    expect(
      await screen.findByText("113 further source-data changes in the same run did not feed this result."),
    ).toBeInTheDocument();
  });
});

describe("accessibility", () => {
  it("labels the section heading and associates it with the section", () => {
    renderSection({ status: "success", data: buildHistoryResponse() });

    const heading = screen.getByRole("heading", { name: copy.SECTION_HEADING });
    expect(heading).toHaveAttribute("id", "test-history-heading");
    expect(heading.closest("section")).toHaveAttribute("aria-labelledby", "test-history-heading");
  });

  it("puts every entry's control in the keyboard tab order", async () => {
    renderSection({
      status: "success",
      data: buildHistoryResponse({
        entries: [buildRecordedEntry({ recorded_result_id: 2 }), buildRecordedEntry({ recorded_result_id: 1 })],
      }),
    });

    // Native <summary> elements are focusable and Enter-activatable by
    // the browser itself -- which is exactly why the row uses one
    // rather than a div with a click handler. jsdom does not implement
    // <details> keyboard toggling, so this asserts the property jsdom
    // CAN observe (both controls are reachable by Tab, in order) rather
    // than simulating a toggle the environment would fake.
    const summaries = screen.getAllByText("July 2026").map((node) => node.closest("summary"));
    expect(summaries).toHaveLength(2);

    await userEvent.tab();
    expect(summaries[0]).toHaveFocus();
    await userEvent.tab();
    expect(summaries[1]).toHaveFocus();
  });

  it("opens an entry through its native disclosure control", async () => {
    renderSection({ status: "success", data: buildHistoryResponse() });

    const details = (screen.getAllByText("July 2026")[0] as HTMLElement).closest("details") as HTMLElement;
    expect(details).not.toHaveAttribute("open");

    await openFirstEntry();

    expect(details).toHaveAttribute("open");
    expect(await screen.findByText(copy.THEN_HEADING)).toBeInTheDocument();
  });

  it("uses a real table with row headers for the then-vs-today figures", async () => {
    mockedGetDetail.mockResolvedValue(buildRevisedDetail());
    renderSection({ status: "success", data: buildHistoryResponse() });
    await openFirstEntry();

    const table = await screen.findByRole("table");
    expect(within(table).getAllByRole("columnheader").map((cell) => cell.textContent)).toEqual([
      "Observation",
      "Then",
      "Today",
      "Status",
    ]);
    expect(within(table).getAllByRole("rowheader").length).toBeGreaterThan(0);
  });

  it("gives the replay badge a screen-reader description beyond its colour", () => {
    renderSection({ status: "success", data: buildHistoryResponse() });

    const badge = screen.getByText("Replay verified").closest("span") as HTMLElement;
    expect(badge.textContent).toMatch(/reproduces this exact result/);
  });
});

describe("no database vocabulary reaches the primary experience", () => {
  it.each(["recorded_to", "recorded_from", "system-time", "temporal", "observation_versions", "half-open"])(
    "never renders %s",
    async (term) => {
      mockedGetDetail.mockResolvedValue(buildRevisedDetail());
      renderSection({ status: "success", data: buildHistoryResponse() });
      await openFirstEntry();
      await screen.findByText(copy.THEN_HEADING);

      expect(document.body.textContent?.toLowerCase()).not.toContain(term.toLowerCase());
    },
  );
});
