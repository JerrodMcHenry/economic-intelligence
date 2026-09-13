/**
 * Integration-level tests for the release calendar product page. Both
 * API calls (`fetchUpcomingReleases`/`fetchRecentReleases`) are mocked
 * at the module boundary -- no live backend required, exactly the
 * pattern pages/Inflation.test.tsx already established.
 */
import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { fetchRecentReleases, fetchUpcomingReleases } from "../api/releases";
import { buildReleaseListResponse, buildReleaseOccurrenceItem } from "../test/fixtures/releases";
import { ReleasesPage } from "./Releases";

vi.mock("../api/releases", () => ({
  fetchUpcomingReleases: vi.fn(),
  fetchRecentReleases: vi.fn(),
}));

const mockedFetchUpcoming = vi.mocked(fetchUpcomingReleases);
const mockedFetchRecent = vi.mocked(fetchRecentReleases);

beforeEach(() => {
  mockedFetchUpcoming.mockReset();
  mockedFetchRecent.mockReset();
});

function resolveBoth(overrides: {
  upcoming?: ReturnType<typeof buildReleaseListResponse>;
  recent?: ReturnType<typeof buildReleaseListResponse>;
} = {}) {
  mockedFetchUpcoming.mockResolvedValue(overrides.upcoming ?? buildReleaseListResponse({ releases: [] }));
  mockedFetchRecent.mockResolvedValue(overrides.recent ?? buildReleaseListResponse({ releases: [] }));
}

function renderPage() {
  return render(<ReleasesPage />);
}

async function findSection(name: string) {
  const heading = await screen.findByRole("heading", { name });
  return heading.closest("section") as HTMLElement;
}

describe("page header and disclosure", () => {
  it("renders the page title and the required disclosure", async () => {
    resolveBoth();
    renderPage();

    expect(screen.getByRole("heading", { level: 1, name: "Economic Releases" })).toBeInTheDocument();
    expect(
      await screen.findByText(
        "Release dates indicate scheduled publication dates. They do not confirm that new data has been published, ingested, or reflected in Economic Intelligence analysis.",
      ),
    ).toBeInTheDocument();
  });
});

describe("loading state", () => {
  it("shows a stable loading indicator for both sections with no fabricated release data", () => {
    mockedFetchUpcoming.mockReturnValue(new Promise(() => {}));
    mockedFetchRecent.mockReturnValue(new Promise(() => {}));
    renderPage();

    expect(screen.getAllByRole("status").length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(/FRED/)).not.toBeInTheDocument();
  });
});

describe("Upcoming Releases", () => {
  it("renders the heading, dates, and names in ascending backend order", async () => {
    resolveBoth({
      upcoming: buildReleaseListResponse({
        releases: [
          buildReleaseOccurrenceItem({ release_id: 1, name: "Consumer Price Index", scheduled_date: "2026-09-20" }),
          buildReleaseOccurrenceItem({ release_id: 2, name: "Employment Situation", scheduled_date: "2026-10-02" }),
        ],
      }),
    });
    renderPage();

    const section = await findSection("Upcoming Releases");
    const names = within(section).getAllByText(/Consumer Price Index|Employment Situation/);
    expect(names.map((el) => el.textContent)).toEqual(["Consumer Price Index", "Employment Situation"]);
    expect(within(section).getByText("20")).toBeInTheDocument();
    expect(within(section).getByText("2")).toBeInTheDocument();
  });

  it("shows the backend's SCHEDULED status directly", async () => {
    resolveBoth({
      upcoming: buildReleaseListResponse({
        releases: [buildReleaseOccurrenceItem({ schedule_status: "SCHEDULED" })],
      }),
    });
    renderPage();

    const section = await findSection("Upcoming Releases");
    expect(within(section).getByText("Scheduled")).toBeInTheDocument();
  });

  it("shows the empty-window message, not an error, for a successful zero-result response", async () => {
    resolveBoth({ upcoming: buildReleaseListResponse({ releases: [] }) });
    renderPage();

    expect(await screen.findByText("No scheduled releases in this window.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a truthful infrastructure error, with retry, on failure", async () => {
    mockedFetchUpcoming.mockRejectedValue(new Error("network down"));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    renderPage();

    expect(await screen.findByText("Upcoming releases could not be loaded.")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Retry" }).length).toBeGreaterThanOrEqual(1);
  });
});

describe("Recent Releases", () => {
  it("renders the heading, dates, and names in descending backend order", async () => {
    resolveBoth({
      recent: buildReleaseListResponse({
        releases: [
          buildReleaseOccurrenceItem({ release_id: 1, name: "Consumer Price Index", scheduled_date: "2026-09-11", schedule_status: "PAST_DUE" }),
          buildReleaseOccurrenceItem({ release_id: 2, name: "Employment Situation", scheduled_date: "2026-09-04", schedule_status: "PAST_DUE" }),
        ],
      }),
    });
    renderPage();

    const section = await findSection("Recent Releases");
    const names = within(section).getAllByText(/Consumer Price Index|Employment Situation/);
    expect(names.map((el) => el.textContent)).toEqual(["Consumer Price Index", "Employment Situation"]);
  });

  it("shows the backend's PAST_DUE status directly", async () => {
    resolveBoth({
      recent: buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem({ schedule_status: "PAST_DUE" })] }),
    });
    renderPage();

    const section = await findSection("Recent Releases");
    expect(within(section).getByText("Past due")).toBeInTheDocument();
  });

  it("shows SCHEDULED as-is for a same-day recent release, without overriding it to Past due", async () => {
    resolveBoth({
      recent: buildReleaseListResponse({
        releases: [buildReleaseOccurrenceItem({ scheduled_date: "2026-09-13", schedule_status: "SCHEDULED" })],
      }),
    });
    renderPage();

    const section = await findSection("Recent Releases");
    expect(within(section).getByText("Scheduled")).toBeInTheDocument();
    expect(within(section).queryByText("Past due")).not.toBeInTheDocument();
  });

  it("shows the empty-window message, not an error, for a successful zero-result response", async () => {
    resolveBoth({ recent: buildReleaseListResponse({ releases: [] }) });
    renderPage();

    expect(await screen.findByText("No recently scheduled releases in this window.")).toBeInTheDocument();
  });

  it("shows a truthful infrastructure error, with retry, on failure", async () => {
    mockedFetchRecent.mockRejectedValue(new Error("network down"));
    mockedFetchUpcoming.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    renderPage();

    expect(await screen.findByText("Recent releases could not be loaded.")).toBeInTheDocument();
  });
});

describe("partial failure resilience", () => {
  it("renders Recent normally when only Upcoming fails", async () => {
    mockedFetchUpcoming.mockRejectedValue(new Error("down"));
    mockedFetchRecent.mockResolvedValue(
      buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem({ name: "Employment Situation" })] }),
    );
    renderPage();

    expect(await screen.findByText("Upcoming releases could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Recent Releases" })).toBeInTheDocument();
    expect(screen.getByText("Employment Situation")).toBeInTheDocument();
  });

  it("renders Upcoming normally when only Recent fails", async () => {
    mockedFetchRecent.mockRejectedValue(new Error("down"));
    mockedFetchUpcoming.mockResolvedValue(
      buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem({ name: "Gross Domestic Product" })] }),
    );
    renderPage();

    expect(await screen.findByText("Recent releases could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Upcoming Releases" })).toBeInTheDocument();
    expect(screen.getByText("Gross Domestic Product")).toBeInTheDocument();
  });
});

describe("no client-side status derivation (trusts the backend even when it looks surprising)", () => {
  it("shows PAST_DUE for a future-dated release when the backend says PAST_DUE", async () => {
    resolveBoth({
      upcoming: buildReleaseListResponse({
        releases: [buildReleaseOccurrenceItem({ scheduled_date: "2099-01-01", schedule_status: "PAST_DUE" })],
      }),
    });
    renderPage();

    const section = await findSection("Upcoming Releases");
    expect(within(section).getByText("Past due")).toBeInTheDocument();
  });

  it("shows SCHEDULED for a past-dated release when the backend says SCHEDULED", async () => {
    resolveBoth({
      recent: buildReleaseListResponse({
        releases: [buildReleaseOccurrenceItem({ scheduled_date: "2000-01-01", schedule_status: "SCHEDULED" })],
      }),
    });
    renderPage();

    const section = await findSection("Recent Releases");
    expect(within(section).getByText("Scheduled")).toBeInTheDocument();
  });
});

describe("semantics: no publication or data-availability claims", () => {
  const FORBIDDEN_WORDS = /\b(released|published|refreshed)\b/i;
  const FORBIDDEN_PHRASES = [/data is now available/i, /data.{0,20}available/i, /new data/i, /analysis refreshed/i, /\bupdated\b/i];

  it("never renders forbidden publication/availability language outside the one mandated disclosure sentence", async () => {
    // The required disclosure text (see pages/Releases.tsx) legitimately
    // contains the word "published" -- but only as a negation ("do not
    // confirm ... has been published"), never as a claim. Excluding
    // that one sanctioned sentence proves nothing ELSE on the page
    // (badges, headings, row text) uses this language.
    resolveBoth({
      upcoming: buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem({ schedule_status: "SCHEDULED" })] }),
      recent: buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem({ schedule_status: "PAST_DUE" })] }),
    });
    renderPage();

    await screen.findByRole("heading", { name: "Upcoming Releases" });
    const disclosure = screen.getByText(/Release dates indicate scheduled publication dates/);
    const bodyText = document.body.textContent ?? "";
    const textOutsideDisclosure = bodyText.replace(disclosure.textContent ?? "", "");

    expect(textOutsideDisclosure).not.toMatch(FORBIDDEN_WORDS);
    for (const pattern of FORBIDDEN_PHRASES) {
      expect(textOutsideDisclosure).not.toMatch(pattern);
    }
  });

  it("the disclosure itself only ever negates publication/availability, never asserts it", async () => {
    resolveBoth();
    renderPage();

    const disclosure = await screen.findByText(/Release dates indicate scheduled publication dates/);
    expect(disclosure.textContent).toMatch(/do not confirm/i);
  });

  it("never renders a time of day anywhere on the page", async () => {
    resolveBoth({ upcoming: buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem()] }) });
    renderPage();

    await screen.findByRole("heading", { name: "Upcoming Releases" });
    const bodyText = document.body.textContent ?? "";
    expect(bodyText).not.toMatch(/\d{1,2}:\d{2}\s*(am|pm)?/i);
  });
});

describe("presentation labels and accessible names", () => {
  it("shows the shortened label for a curated release with long-name entries, preserving the canonical name accessibly", async () => {
    resolveBoth({
      upcoming: buildReleaseListResponse({
        releases: [
          buildReleaseOccurrenceItem({
            provider_release_id: "192",
            name: "Job Openings and Labor Turnover Survey",
          }),
        ],
      }),
    });
    renderPage();

    const section = await findSection("Upcoming Releases");
    expect(within(section).getByText("JOLTS")).toBeInTheDocument();
    expect(within(section).getByText("JOLTS")).toHaveAttribute("aria-label", "Job Openings and Labor Turnover Survey");
  });

  it("shows the canonical name unchanged for a release with no shortening entry", async () => {
    resolveBoth({
      upcoming: buildReleaseListResponse({
        releases: [buildReleaseOccurrenceItem({ provider_release_id: "10", name: "Consumer Price Index" })],
      }),
    });
    renderPage();

    const section = await findSection("Upcoming Releases");
    expect(within(section).getByText("Consumer Price Index")).toBeInTheDocument();
  });

  it("shows the category tag for a curated release", async () => {
    resolveBoth({
      upcoming: buildReleaseListResponse({
        releases: [buildReleaseOccurrenceItem({ provider_release_id: "10", name: "Consumer Price Index" })],
      }),
    });
    renderPage();

    const section = await findSection("Upcoming Releases");
    expect(within(section).getByText("Inflation")).toBeInTheDocument();
  });

  it("shows no category tag for a release outside the curated V1 map", async () => {
    resolveBoth({
      upcoming: buildReleaseListResponse({
        releases: [buildReleaseOccurrenceItem({ provider_release_id: "999", name: "Some Future Release" })],
      }),
    });
    renderPage();

    await screen.findByText("Some Future Release");
    expect(screen.queryByText("Inflation")).not.toBeInTheDocument();
  });
});

describe("accessibility and structure", () => {
  it("uses a single h1 and distinct h2 section headings for Upcoming and Recent", async () => {
    resolveBoth();
    renderPage();

    await screen.findByRole("heading", { name: "Upcoming Releases" });
    expect(screen.getByRole("heading", { level: 1, name: "Economic Releases" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Upcoming Releases" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Recent Releases" })).toBeInTheDocument();
  });

  it("labels each section landmark via aria-labelledby, not just visual position", async () => {
    resolveBoth();
    renderPage();

    const upcomingSection = await findSection("Upcoming Releases");
    const recentSection = await findSection("Recent Releases");
    expect(upcomingSection).toHaveAttribute("aria-labelledby");
    expect(recentSection).toHaveAttribute("aria-labelledby");
    expect(upcomingSection.getAttribute("aria-labelledby")).not.toBe(recentSection.getAttribute("aria-labelledby"));
  });

  it("renders Upcoming before Recent in reading order", async () => {
    resolveBoth();
    renderPage();

    await screen.findByRole("heading", { name: "Upcoming Releases" });
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(["Upcoming Releases", "Recent Releases"]);
  });
});
