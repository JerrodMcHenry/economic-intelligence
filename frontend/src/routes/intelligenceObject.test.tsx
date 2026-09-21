/**
 * The permanent intelligence route (Increment #40).
 *
 * Covers the three outcomes the route is responsible for: a real
 * object resolves, an address with nothing behind it says so honestly
 * without being indexed, and a genuine fault is never disguised as
 * "not found".
 */
import { render, screen, waitFor } from "@testing-library/react";
import { createRoutesStub } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/errors";
import * as api from "../api/intelligence";
import type { RatesMovementIntelligence } from "../api/intelligence.types";
import { ThemeProvider } from "../theme/ThemeProvider";
import Route, { ErrorBoundary, clientLoader, meta } from "./intelligenceObject";

const ID = "rates:UST_NOMINAL_10Y:2026-09-18";

const OBJECT: RatesMovementIntelligence = {
  id: ID,
  type: "RATES_MOVEMENT",
  world: "rates",
  concepts: ["UST_NOMINAL_10Y"],
  effective_period: "2026-09-18",
  recorded_at: "2026-09-20T00:06:45.423250Z",
  published_at: null,
  knowledge_basis: "OBSERVED",
  basis: "METHODOLOGY_DERIVED",
  methodology: { methodology_id: "rates_v1.0", data_basis: "latest_published_data" },
  evidence: [
    {
      concept_id: "UST_NOMINAL_10Y",
      provider: "TREASURY",
      provider_series_id: "UST_NOMINAL_10Y",
      observation_date: "2026-09-18",
      value: 5.01,
    },
  ],
  relations: [],
  limitations: ["Carries no significance claim."],
  contract_version: "intelligence_v1",
  payload: {
    series_title: "10-Year Treasury Par Yield (Nominal)",
    latest_value: 5.01,
    changes: [
      { window: "1_SESSION", sessions: 1, available: true, change_basis_points: 7, from_date: "2026-09-17", from_value: 4.94 },
    ],
    historical_percentile_rank: 0.7699,
    historical_magnitude_percentile_rank: 0.7168,
    historical_observation_count: 113,
  },
};

function renderAt(data: { object: RatesMovementIntelligence | null; intelligenceId: string }) {
  const Stub = createRoutesStub([
    { path: "/intelligence/:intelligenceId", Component: Route, loader: () => data, ErrorBoundary },
  ]);
  render(
    <ThemeProvider>
      <Stub initialEntries={[`/intelligence/${encodeURIComponent(data.intelligenceId)}`]} />
    </ThemeProvider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("resolving an object", () => {
  it("renders a real object at its permanent address", async () => {
    renderAt({ object: OBJECT, intelligenceId: ID });
    // #40B: the consumer name leads; the provider's title moved below it.
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("10-year Treasury yield");
  });

  it("offers the object for sharing", async () => {
    renderAt({ object: OBJECT, intelligenceId: ID });
    expect(await screen.findByRole("button", { name: /share/i })).toBeInTheDocument();
  });

  it("asks the API for the id in the URL, decoded", async () => {
    const get = vi.spyOn(api, "getIntelligenceObject").mockResolvedValue(OBJECT);
    await clientLoader({ params: { intelligenceId: ID } });
    expect(get).toHaveBeenCalledWith(ID);
  });
});

describe("an address with nothing behind it", () => {
  it("turns a 404 into a not-found state rather than an error", async () => {
    vi.spyOn(api, "getIntelligenceObject").mockRejectedValue(new ApiError("http", "not found", 404));
    const data = await clientLoader({ params: { intelligenceId: "rates:NOPE:2026-01-01" } });
    expect(data.object).toBeNull();
  });

  it("says so in plain words, and offers a way out", async () => {
    renderAt({ object: null, intelligenceId: "rates:NOPE:2026-01-01" });
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("No intelligence here");
    expect(screen.getByRole("link", { name: /Go to MacroChipz/ })).toHaveAttribute("href", "/");
  });

  it("asks not to be indexed, so a mistyped link never enters search results", () => {
    const tags = meta({ data: { object: null, intelligenceId: "rates:NOPE:2026-01-01" } });
    expect(tags).toContainEqual({ name: "robots", content: "noindex" });
  });

  it("emits no og:image for an object that does not exist", () => {
    const tags = meta({ data: { object: null, intelligenceId: "x" } });
    expect(tags.some((tag) => tag.property === "og:image")).toBe(false);
  });
});

describe("a genuine fault", () => {
  it("is rethrown, never swallowed into an empty page", async () => {
    // Anything that is not a 404 means the backend is broken. This one
    // function serves BOTH modes -- it runs in Node at prerender time
    // and in the browser afterwards (#40A) -- so rethrowing here is
    // what fails a release build and what surfaces the ErrorBoundary
    // in the browser. A prerender that swallowed this would ship a
    // permanent URL with no content behind it.
    vi.spyOn(api, "getIntelligenceObject").mockRejectedValue(new ApiError("http", "upstream down", 503));
    await expect(clientLoader({ params: { intelligenceId: ID } })).rejects.toThrow("upstream down");
  });

  it("tells the reader it is our problem, not their link", () => {
    const Stub = createRoutesStub([
      {
        path: "/intelligence/:intelligenceId",
        Component: Route,
        loader() {
          throw new Error("upstream down");
        },
        ErrorBoundary,
      },
    ]);
    render(
      <ThemeProvider>
        <Stub initialEntries={[`/intelligence/${encodeURIComponent(ID)}`]} />
      </ThemeProvider>,
    );
    return waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("This could not be loaded");
      expect(screen.getByText(/a problem on our side, not with the link/)).toBeInTheDocument();
    });
  });
});
