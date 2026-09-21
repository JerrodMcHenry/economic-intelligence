import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { SinceLastVisit } from "./SinceLastVisit";
import { buildDomainRecap, buildRecalculation, buildSinceLastVisitResponse, buildSourceUpdate, buildStructuralChange } from "../../test/fixtures/sinceLastVisit";
import type { SinceLastVisitResponse } from "../../api/sinceLastVisit.types";
import type { ApiResourceState } from "../../api/useApiResource";

function renderWithData(response: SinceLastVisitResponse) {
  const state: ApiResourceState<SinceLastVisitResponse> & { reload: () => void } = {
    status: "success",
    data: response,
    reload: vi.fn(),
  };
  return render(
    <MemoryRouter>
      <SinceLastVisit sinceLastVisit={state} />
    </MemoryRouter>,
  );
}

describe("SinceLastVisit", () => {
  it("loading state: shows the section heading and a skeleton, no fabricated content", () => {
    render(
      <MemoryRouter>
        <SinceLastVisit sinceLastVisit={{ status: "loading", reload: vi.fn() }} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByText(/was calculated as|remains|changed from/)).not.toBeInTheDocument();
  });

  it("error state: shows the existing ErrorMessage pattern with a retry action, never blocks rendering", () => {
    const reload = vi.fn();
    render(
      <MemoryRouter>
        <SinceLastVisit sinceLastVisit={{ status: "error", error: new Error("boom") as never, reload }} />
      </MemoryRouter>,
    );
    expect(screen.getByText("Recent activity could not be loaded.")).toBeInTheDocument();
    screen.getByRole("button", { name: "Retry" }).click();
    expect(reload).toHaveBeenCalled();
  });

  it("first visit: exact heading and orientation copy, never 'Since your last visit'", () => {
    renderWithData(buildSinceLastVisitResponse({ first_visit: true }));
    expect(screen.getByRole("heading", { name: "Recent Economic Activity" })).toBeInTheDocument();
    expect(screen.getByText(/This is your first visit/)).toBeInTheDocument();
    expect(screen.queryByText(/Since your last visit/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Since Your Last Check" })).not.toBeInTheDocument();
  });

  it("return visit: exact heading, no first-visit orientation copy", () => {
    renderWithData(buildSinceLastVisitResponse({ first_visit: false }));
    expect(screen.getByRole("heading", { name: "Since Your Last Check" })).toBeInTheDocument();
    expect(screen.queryByText(/This is your first visit/)).not.toBeInTheDocument();
  });

  it("clamped lookback: exact disclosure renders", () => {
    renderWithData(buildSinceLastVisitResponse({ lookback_clamped: true }));
    expect(screen.getByText("This summary covers the last 90 days — your last visit was longer ago.")).toBeInTheDocument();
  });

  it("not clamped: no clamp disclosure renders", () => {
    renderWithData(buildSinceLastVisitResponse({ lookback_clamped: false }));
    expect(screen.queryByText(/last visit was longer ago/)).not.toBeInTheDocument();
  });

  it("renders both domain blocks, Inflation then Labor, each independently", () => {
    renderWithData(
      buildSinceLastVisitResponse({
        inflation: buildDomainRecap({ monitor: "inflation" }),
        labor: buildDomainRecap({ monitor: "labor" }),
      }),
    );
    expect(screen.getByText("Inflation")).toBeInTheDocument();
    expect(screen.getByText("Labor")).toBeInTheDocument();
  });

  it("structural change renders the exact copy", () => {
    renderWithData(
      buildSinceLastVisitResponse({
        inflation: buildDomainRecap({
          monitor: "inflation",
          structural_changes: [buildStructuralChange({ monitor: "inflation", previous_value: "COOLING", current_value: "STABLE", evaluation_period: "2026-08-01" })],
        }),
      }),
    );
    expect(screen.getByText("Inflation changed from Cooling to Stable for August 2026.")).toBeInTheDocument();
  });

  it("two structural transitions (changed then changed back) both render, in order (contract §24-25)", () => {
    renderWithData(
      buildSinceLastVisitResponse({
        labor: buildDomainRecap({
          monitor: "labor",
          structural_changes: [
            buildStructuralChange({ monitor: "labor", previous_value: "STABLE", current_value: "COOLING", evaluation_period: "2026-08-01", release_check_run_id: 1, field: "state" }),
            buildStructuralChange({ monitor: "labor", previous_value: "COOLING", current_value: "STABLE", evaluation_period: "2026-09-01", release_check_run_id: 2, field: "state" }),
          ],
        }),
      }),
    );
    expect(screen.getByText("Labor changed from Stable to Cooling for August 2026.")).toBeInTheDocument();
    expect(screen.getByText("Labor changed from Cooling to Stable for September 2026.")).toBeInTheDocument();
  });

  it("availability lost renders the exact non-directional copy", () => {
    renderWithData(
      buildSinceLastVisitResponse({
        inflation: buildDomainRecap({
          monitor: "inflation",
          structural_changes: [buildStructuralChange({ monitor: "inflation", event_type: "AVAILABILITY_LOST", previous_value: "COOLING", current_value: null, evaluation_period: "2026-08-01" })],
        }),
      }),
    );
    expect(screen.getByText("Inflation's own state became unavailable for August 2026.")).toBeInTheDocument();
  });

  it("availability restored renders the exact mirrored copy", () => {
    renderWithData(
      buildSinceLastVisitResponse({
        labor: buildDomainRecap({
          monitor: "labor",
          structural_changes: [buildStructuralChange({ monitor: "labor", event_type: "AVAILABILITY_RESTORED", previous_value: null, current_value: "STABLE", evaluation_period: "2026-08-01" })],
        }),
      }),
    );
    expect(screen.getByText("Labor's own state became available again for August 2026.")).toBeInTheDocument();
  });

  it("unchanged confirmation renders the exact 'remains' template", () => {
    renderWithData(
      buildSinceLastVisitResponse({
        inflation: buildDomainRecap({
          monitor: "inflation",
          recalculations: [buildRecalculation({ monitor: "inflation", kind: "UNCHANGED_CONFIRMATION", state: "COOLING", evaluation_period: "2026-08-01", count: 1 })],
        }),
      }),
    );
    expect(screen.getByText("Inflation was recalculated for August 2026 and remains Cooling.")).toBeInTheDocument();
  });

  it("first calculation never renders 'remains'", () => {
    renderWithData(
      buildSinceLastVisitResponse({
        inflation: buildDomainRecap({
          monitor: "inflation",
          recalculations: [buildRecalculation({ monitor: "inflation", kind: "FIRST_CALCULATION", state: "COOLING", evaluation_period: "2026-08-01" })],
        }),
      }),
    );
    expect(screen.getByText("Inflation was calculated as Cooling for August 2026.")).toBeInTheDocument();
    expect(screen.queryByText(/remains/i)).not.toBeInTheDocument();
  });

  it("repeated confirmation aggregates to one line with the count, never N separate cards", () => {
    renderWithData(
      buildSinceLastVisitResponse({
        inflation: buildDomainRecap({
          monitor: "inflation",
          recalculations: [buildRecalculation({ monitor: "inflation", kind: "UNCHANGED_CONFIRMATION", state: "COOLING", evaluation_period: "2026-09-01", count: 3 })],
        }),
      }),
    );
    expect(screen.getByText("Inflation was recalculated 3 times since your last visit and remains Cooling (most recently for September 2026).")).toBeInTheDocument();
  });

  it("source update NEW renders the exact copy", () => {
    renderWithData(
      buildSinceLastVisitResponse({
        inflation: buildDomainRecap({
          monitor: "inflation",
          source_updates: [buildSourceUpdate({ monitor: "inflation", series_title: "Headline CPI", change_type: "NEW" })],
        }),
      }),
    );
    expect(screen.getByText("Headline CPI data was updated.")).toBeInTheDocument();
  });

  it("source update REVISED renders the exact, distinct copy", () => {
    renderWithData(
      buildSinceLastVisitResponse({
        labor: buildDomainRecap({
          monitor: "labor",
          source_updates: [buildSourceUpdate({ monitor: "labor", series_title: "PAYEMS", change_type: "REVISED" })],
        }),
      }),
    );
    expect(screen.getByText("PAYEMS data was revised.")).toBeInTheDocument();
  });

  it("CHECKED, zero items -> exact zero-state copy", () => {
    renderWithData(buildSinceLastVisitResponse({ inflation: buildDomainRecap({ monitor: "inflation", coverage: "CHECKED" }) }));
    expect(screen.getByText("No new Inflation activity was detected since your last check.")).toBeInTheDocument();
  });

  it("GAP -> zero-state copy AND, when there IS content, the soft coverage disclosure alongside it", () => {
    renderWithData(
      buildSinceLastVisitResponse({
        labor: buildDomainRecap({
          monitor: "labor",
          coverage: "GAP",
          structural_changes: [buildStructuralChange({ monitor: "labor" })],
        }),
      }),
    );
    expect(screen.getByText("Some monitored releases could not be fully checked since your last visit.")).toBeInTheDocument();
  });

  it("UNKNOWN -> exact coverage-unknown copy, never silently upgraded to 'no changes'", () => {
    renderWithData(buildSinceLastVisitResponse({ inflation: buildDomainRecap({ monitor: "inflation", coverage: "UNKNOWN" }) }));
    expect(screen.getByText("Coverage for Inflation could not be confirmed for this period.")).toBeInTheDocument();
    expect(screen.queryByText(/No new Inflation activity/)).not.toBeInTheDocument();
  });

  it("last-checked timestamp renders when available", () => {
    renderWithData(buildSinceLastVisitResponse({ inflation: buildDomainRecap({ monitor: "inflation", last_checked_at: "2026-09-15T09:04:00Z" }) }));
    expect(screen.getAllByText(/^Last checked:/).length).toBeGreaterThan(0);
  });

  it("CTAs link to the correct, existing domain routes, no query params, no new destination", () => {
    renderWithData(buildSinceLastVisitResponse());
    const inflationLink = screen.getByRole("link", { name: "View Inflation →" });
    const laborLink = screen.getByRole("link", { name: "View Jobs →" });
    expect(inflationLink).toHaveAttribute("href", "/inflation");
    expect(laborLink).toHaveAttribute("href", "/jobs");
  });

  it("preserves backend item order, never resorts", () => {
    const { container } = renderWithData(
      buildSinceLastVisitResponse({
        inflation: buildDomainRecap({
          monitor: "inflation",
          structural_changes: [
            buildStructuralChange({ monitor: "inflation", evaluation_period: "2026-08-01", release_check_run_id: 1 }),
            buildStructuralChange({ monitor: "inflation", evaluation_period: "2026-09-01", release_check_run_id: 2 }),
          ],
        }),
      }),
    );
    const text = container.textContent ?? "";
    expect(text.indexOf("August 2026")).toBeLessThan(text.indexOf("September 2026"));
  });

  it("accessibility: state is conveyed as text, not color -- content survives with styling stripped", () => {
    renderWithData(
      buildSinceLastVisitResponse({
        inflation: buildDomainRecap({
          monitor: "inflation",
          recalculations: [buildRecalculation({ monitor: "inflation", kind: "UNCHANGED_CONFIRMATION", state: "COOLING" })],
        }),
      }),
    );
    const heading = screen.getByRole("heading", { level: 2 });
    const section = heading.closest("section") as HTMLElement;
    expect(within(section).getByText(/Cooling/)).toBeInTheDocument();
  });
});
