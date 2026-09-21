/**
 * The permanent intelligence page (Increment #40, consumer pass #40B).
 *
 * Asserts what the page promises: SEE -> UNDERSTAND -> CONTEXT ->
 * EXPLORE -> VERIFY -> SHARE is present and in that order, machine
 * taxonomy is translated, the historical comparison states its own
 * scope, and nothing dishonest is displayed -- an unknown publication
 * time stays unknown, and no causal or significance claim appears.
 */
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { __setProviderForTests } from "../../analytics/track";
import type { RatesMovementIntelligence } from "../../api/intelligence.types";
import { IntelligenceSee } from "./IntelligenceSee";
import { IntelligenceVerify } from "./IntelligenceVerify";
import { ShareButton } from "../ShareButton";

const OBJECT: RatesMovementIntelligence = {
  id: "rates:UST_NOMINAL_10Y:2026-09-18",
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
  limitations: [
    "Carries no significance claim: rates_v1.0 defines no notability threshold, so this reports the movement and its own historical position, not that the movement matters.",
    "Change windows are counted in trading SESSIONS, never calendar days.",
  ],
  contract_version: "intelligence_v1",
  // The real payload for this object, copied from the API rather than
  // invented, so the consumer copy is asserted against numbers the
  // engine actually produces.
  payload: {
    series_title: "10-Year Treasury Par Yield (Nominal)",
    latest_value: 5.01,
    changes: [
      { window: "1_SESSION", sessions: 1, available: true, change_basis_points: 7, from_date: "2026-09-17", from_value: 4.94 },
      { window: "5_SESSIONS", sessions: 5, available: true, change_basis_points: 5, from_date: "2026-09-11", from_value: 4.96 },
      { window: "21_SESSIONS", sessions: 21, available: true, change_basis_points: 36, from_date: "2026-08-19", from_value: 4.65 },
      { window: "63_SESSIONS", sessions: 63, available: true, change_basis_points: 55, from_date: "2026-06-18", from_value: 4.46 },
    ],
    historical_percentile_rank: 0.566372,
    historical_magnitude_percentile_rank: 0.39823,
    historical_observation_count: 113,
    visual_evidence: {
      kind: "TIME_SERIES",
      concept_id: "UST_NOMINAL_10Y",
      unit: "Percent",
      requested_sessions: 63,
      available_sessions: 3,
      points: [
        { observation_date: "2026-06-22", value: 4.51 },
        { observation_date: "2026-08-10", value: 4.72 },
        { observation_date: "2026-09-18", value: 5.01 },
      ],
    },
  },
};

afterEach(() => {
  __setProviderForTests(null);
  vi.restoreAllMocks();
});

function renderSee() {
  return render(
    <MemoryRouter>
      <IntelligenceSee object={OBJECT} />
    </MemoryRouter>,
  );
}

describe("SEE — the first viewport", () => {
  it("leads with a name a reader recognises, not the provider's title", () => {
    renderSee();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("10-year Treasury yield");
  });

  it("shows the value as the dominant number", () => {
    renderSee();
    expect(screen.getByText("5.01%")).toBeInTheDocument();
  });

  it("states the movement in PERCENTAGE POINTS, not basis points", () => {
    renderSee();
    // 5 bp over 5 sessions -> 0.05 percentage points.
    expect(screen.getByText(/Up 0\.05 percentage points/)).toBeInTheDocument();
    expect(screen.getByText(/over the last 5 trading days/)).toBeInTheDocument();
  });

  it("keeps the provider's exact title available, just not first", () => {
    renderSee();
    const title = screen.getByText("10-Year Treasury Par Yield (Nominal)");
    expect(title).toBeInTheDocument();
    expect(title.tagName).not.toBe("H1");
  });

  it("names the world and the period", () => {
    // The eyebrow specifically -- not the "Explore Rates" link below,
    // nor the chart's data table, which also lists this date.
    const { container } = renderSee();
    expect(container.querySelector("header p")).toHaveTextContent("Rates · 2026-09-18");
  });

  it("translates machine taxonomy into consumer language", () => {
    const { container } = renderSee();
    const text = container.textContent ?? "";
    for (const jargon of ["RATES_MOVEMENT", "METHODOLOGY_DERIVED", "SOURCE_FACT", "OBSERVED", "UST_NOMINAL_10Y"]) {
      expect(text, jargon).not.toContain(jargon);
    }
  });

  it("conveys direction by word, never by colour or arrow alone", () => {
    renderSee();
    // The headline says "Up" in words; the arrow is aria-hidden.
    expect(screen.getByText(/^Up 0\.05 percentage points$/)).toBeInTheDocument();
    // Every window in the grid carries a screen-reader direction word.
    expect(screen.getAllByText("(up)", { selector: ".sr-only" })).toHaveLength(4);
  });
});

describe("UNDERSTAND — Why this matters", () => {
  it("shows a curated explanation selected by concept id", () => {
    renderSee();
    expect(screen.getByRole("heading", { name: "Why this matters" })).toBeInTheDocument();
    expect(screen.getByText(/What the U\.S\. government pays to borrow for ten years/)).toBeInTheDocument();
  });

  it("describes the benchmark relationship as influence, never as control", () => {
    const { container } = renderSee();
    const text = container.textContent ?? "";
    expect(text).toContain("reference point, not a mechanism");
    expect(text).toContain("does not set any of those rates");
  });

  it("makes no causal claim about why today's number moved", () => {
    const { container } = renderSee();
    const text = (container.textContent ?? "").toLowerCase();
    for (const causal of ["because of", "driven by", "caused by", "due to", "in response to", "on fears", "after the fed"]) {
      expect(text, causal).not.toContain(causal);
    }
  });

  it("shows nothing at all for a concept with no curated entry", () => {
    render(
      <MemoryRouter>
        <IntelligenceSee object={{ ...OBJECT, concepts: ["UST_NOMINAL_7Y"] }} />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("heading", { name: "Why this matters" })).not.toBeInTheDocument();
    // ...and falls back to the provider's own title rather than inventing a friendly one.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("10-Year Treasury Par Yield (Nominal)");
  });
});

describe("CONTEXT — how far it moved", () => {
  it("shows every available window in percentage points", () => {
    renderSee();
    expect(screen.getByText("the last 5 trading days")).toBeInTheDocument();
    expect(screen.getByText("the last 21 trading days")).toBeInTheDocument();
    expect(screen.getByText("+0.05")).toBeInTheDocument();
    expect(screen.getByText("+0.36")).toBeInTheDocument();
  });

  it("keeps basis points available beside them as technical detail", () => {
    renderSee();
    expect(screen.getByText("+5 bp")).toBeInTheDocument();
    expect(screen.getByText("+36 bp")).toBeInTheDocument();
  });

  it("says windows are trading days, not calendar days", () => {
    renderSee();
    expect(screen.getByText(/count published trading days, never calendar days/)).toBeInTheDocument();
  });
});

describe("CONTEXT — is this unusual?", () => {
  it("asks the consumer question", () => {
    renderSee();
    expect(screen.getByRole("heading", { name: "Is this unusual?" })).toBeInTheDocument();
  });

  it("states what is compared: the MOVE, not the level", () => {
    const { container } = renderSee();
    const text = container.textContent ?? "";
    expect(text).toContain("move over 5 trading days");
    expect(text).toContain("not the level itself");
    // #40 said "this level sits at the Nth percentile", which named the
    // wrong quantity entirely: rates_v1.0 ranks the 5-session CHANGE.
    expect(text).not.toMatch(/this level sits at/i);
  });

  it("distinguishes the signed rank from the magnitude rank", () => {
    renderSee();
    expect(screen.getByText("Direction and size together:")).toBeInTheDocument();
    expect(screen.getByText("Size alone, ignoring direction:")).toBeInTheDocument();
    expect(screen.getByText("larger than 57% of them")).toBeInTheDocument();
    expect(screen.getByText("larger than 40% of them")).toBeInTheDocument();
  });

  it("states how much history the comparison actually has", () => {
    renderSee();
    expect(screen.getByText(/113 earlier 5-trading-day moves in this yield/)).toBeInTheDocument();
  });

  it("refuses to present a short record as long-run history", () => {
    const { container } = renderSee();
    const text = container.textContent ?? "";
    expect(text).toContain("a few months of trading, not decades");
    expect(text).toContain("not a statement about what is normal for this yield over the long run");
  });

  it("assigns no significance label, because no methodology defines one", () => {
    const { container } = renderSee();
    const text = container.textContent ?? "";
    expect(text).toContain("does not label this move unusual or ordinary");
    expect(text).toMatch(/defines no threshold/);
  });

  it("renders nothing when the object carries no historical context", () => {
    render(
      <MemoryRouter>
        <IntelligenceSee
          object={{
            ...OBJECT,
            payload: {
              ...OBJECT.payload,
              historical_percentile_rank: null,
              historical_magnitude_percentile_rank: null,
            },
          }}
        />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("heading", { name: "Is this unusual?" })).not.toBeInTheDocument();
  });
});

describe("the #40B/#40C hierarchy holds", () => {
  it("presents SEE -> VISUAL EVIDENCE -> UNDERSTAND -> CONTEXT -> EXPLORE in that order", () => {
    const { container } = renderSee();
    const order = [...container.querySelectorAll("h1, h2, figure")].map((element) =>
      element.tagName === "FIGURE" ? "VISUAL EVIDENCE" : (element.textContent ?? "").trim(),
    );
    expect(order).toEqual([
      "10-year Treasury yield",
      "VISUAL EVIDENCE",
      "Why this matters",
      "How far it has moved",
      "Is this unusual?",
    ]);
  });

  it("puts the chart after the headline number, not before it", () => {
    const { container } = renderSee();
    const heading = container.querySelector("h1");
    const figure = container.querySelector("figure");
    expect(heading && figure && heading.compareDocumentPosition(figure) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("renders no chart when the object carries no visual evidence", () => {
    render(
      <MemoryRouter>
        <IntelligenceSee object={{ ...OBJECT, payload: { ...OBJECT.payload, visual_evidence: null } }} />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("figure")).not.toBeInTheDocument();
    // ...and the rest of the page is unaffected.
    expect(screen.getByRole("heading", { name: "Is this unusual?" })).toBeInTheDocument();
  });
});

describe("EXPLORE", () => {
  it("offers a restrained path into the Rates world", () => {
    renderSee();
    expect(screen.getByRole("link", { name: /Explore Rates/ })).toHaveAttribute("href", "/rates");
  });
});

describe("VERIFY", () => {
  it("keeps evidence behind progressive disclosure, not dumped on the page", () => {
    render(<IntelligenceVerify object={OBJECT} />);
    const summary = screen.getByText(/^Evidence \(1\)$/);
    expect(summary.closest("details")).not.toHaveAttribute("open");
  });

  it("shows the actual provider and their own series identifier", () => {
    render(<IntelligenceVerify object={OBJECT} />);
    const table = screen.getByRole("table");
    expect(within(table).getByText("TREASURY")).toBeInTheDocument();
    expect(within(table).getByText("5.01")).toBeInTheDocument();
  });

  it("does not fabricate a publication time when the source did not give one", () => {
    render(<IntelligenceVerify object={OBJECT} />);
    expect(screen.getByText(/Not known — the source does not publish an exact time/)).toBeInTheDocument();
  });

  it("carries the methodology version, in both consumer and exact form", () => {
    render(<IntelligenceVerify object={OBJECT} />);
    // The reader is told who calculated this in plain words...
    expect(screen.getByText("Calculated by MacroChipz (rates_v1.0)")).toBeInTheDocument();
    // ...and the exact frozen version is available to check against.
    expect(screen.getByText("rates_v1.0 (latest_published_data)")).toBeInTheDocument();
  });

  it("shows the object's own limitations honestly", () => {
    render(<IntelligenceVerify object={OBJECT} />);
    expect(screen.getByText(/Carries no significance claim/)).toBeInTheDocument();
  });

  it("emits evidence_expanded through the analytics abstraction", () => {
    const sent: string[] = [];
    __setProviderForTests({ name: "recording", send: (event) => sent.push(event) });
    render(<IntelligenceVerify object={OBJECT} />);
    const details = screen.getByText(/^Evidence \(1\)$/).closest("details")!;
    details.open = true;
    details.dispatchEvent(new Event("toggle"));
    expect(sent).toContain("evidence_expanded");
  });
});

describe("SHARE", () => {
  const url = "https://macrochipz.example/intelligence/rates%3AUST_NOMINAL_10Y%3A2026-09-18";

  it("uses the platform share sheet when available", async () => {
    const share = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { share, clipboard: { writeText: vi.fn() } });
    render(<ShareButton objectType="RATES_MOVEMENT" title="t" url={url} />);
    await userEvent.click(screen.getByRole("button", { name: /share/i }));
    expect(share).toHaveBeenCalledWith({ title: "t", url });
  });

  it("falls back to copying the permanent URL when there is no share sheet", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    render(<ShareButton objectType="RATES_MOVEMENT" title="t" url={url} />);
    await userEvent.click(screen.getByRole("button", { name: /share/i }));
    expect(writeText).toHaveBeenCalledWith(url);
    expect(await screen.findByText("Link copied")).toBeInTheDocument();
  });

  it("shares the permanent URL unmodified, with no tracking parameters", async () => {
    const share = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { share });
    render(<ShareButton objectType="RATES_MOVEMENT" title="t" url={url} />);
    await userEvent.click(screen.getByRole("button", { name: /share/i }));
    expect(share.mock.calls[0]?.[0]?.url).toBe(url);
  });

  it("emits share_initiated with the object type only", async () => {
    const sent: Array<{ event: string; props: Record<string, unknown> }> = [];
    __setProviderForTests({ name: "recording", send: (event, props) => sent.push({ event, props: { ...props } }) });
    vi.stubGlobal("navigator", { share: vi.fn().mockResolvedValue(undefined) });
    render(<ShareButton objectType="RATES_MOVEMENT" title="t" url={url} />);
    await userEvent.click(screen.getByRole("button", { name: /share/i }));
    const recorded = sent.find((entry) => entry.event === "share_initiated");
    expect(recorded?.props).toEqual({ object_type: "RATES_MOVEMENT" });
    // Never the URL, the title, or the clipboard.
    expect(JSON.stringify(recorded?.props)).not.toContain("macrochipz.example");
  });

  it("still shares when analytics throws", async () => {
    __setProviderForTests({
      name: "exploding",
      send() {
        throw new Error("blocked");
      },
    });
    const share = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { share });
    render(<ShareButton objectType="RATES_MOVEMENT" title="t" url={url} />);
    await userEvent.click(screen.getByRole("button", { name: /share/i }));
    expect(share).toHaveBeenCalled();
  });

  it("still shares when analytics is disabled entirely", async () => {
    __setProviderForTests(null);
    const share = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { share });
    render(<ShareButton objectType="RATES_MOVEMENT" title="t" url={url} />);
    await userEvent.click(screen.getByRole("button", { name: /share/i }));
    expect(share).toHaveBeenCalled();
  });

  it("is reachable and operable from the keyboard", async () => {
    const share = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { share });
    render(<ShareButton objectType="RATES_MOVEMENT" title="t" url={url} />);
    await userEvent.tab();
    expect(screen.getByRole("button", { name: /share/i })).toHaveFocus();
    await userEvent.keyboard("{Enter}");
    expect(share).toHaveBeenCalled();
  });
});
