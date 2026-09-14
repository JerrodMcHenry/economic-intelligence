/**
 * Integration-level tests for the release calendar product page. Both
 * API calls (`fetchUpcomingReleases`/`fetchRecentReleases`) are mocked
 * at the module boundary -- no live backend required, exactly the
 * pattern pages/Inflation.test.tsx already established.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
    const names = within(section).getAllByText(/Consumer Price Index|Employment Situation/, { selector: "span" });
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
    expect(within(section).getByText("Scheduled", { selector: "span" })).toBeInTheDocument();
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

  it("Increment #22B: never renders the per-row monitor/releases CTA here -- it would be circular, already on /releases (§17's rendering-context note)", async () => {
    resolveBoth({
      upcoming: buildReleaseListResponse({
        releases: [
          buildReleaseOccurrenceItem({ release_id: 1, name: "Consumer Price Index", provider_release_id: "10" }),
          buildReleaseOccurrenceItem({ release_id: 2, name: "Job Openings and Labor Turnover Survey", provider_release_id: "192" }),
        ],
      }),
    });
    renderPage();

    await screen.findByText("Consumer Price Index");
    expect(screen.queryByRole("link", { name: "View Inflation →" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "View Labor →" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "View Releases →" })).not.toBeInTheDocument();
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
    const names = within(section).getAllByText(/Consumer Price Index|Employment Situation/, { selector: "span" });
    expect(names.map((el) => el.textContent)).toEqual(["Consumer Price Index", "Employment Situation"]);
  });

  it("shows the backend's PAST_DUE status directly", async () => {
    resolveBoth({
      recent: buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem({ schedule_status: "PAST_DUE" })] }),
    });
    renderPage();

    const section = await findSection("Recent Releases");
    expect(within(section).getByText("Past due", { selector: "span" })).toBeInTheDocument();
  });

  it("shows SCHEDULED as-is for a same-day recent release, without overriding it to Past due", async () => {
    resolveBoth({
      recent: buildReleaseListResponse({
        releases: [buildReleaseOccurrenceItem({ scheduled_date: "2026-09-13", schedule_status: "SCHEDULED" })],
      }),
    });
    renderPage();

    const section = await findSection("Recent Releases");
    expect(within(section).getByText("Scheduled", { selector: "span" })).toBeInTheDocument();
    expect(within(section).queryByText("Past due", { selector: "span" })).not.toBeInTheDocument();
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
    expect(within(section).getByText("Past due", { selector: "span" })).toBeInTheDocument();
  });

  it("shows SCHEDULED for a past-dated release when the backend says SCHEDULED", async () => {
    resolveBoth({
      recent: buildReleaseListResponse({
        releases: [buildReleaseOccurrenceItem({ scheduled_date: "2000-01-01", schedule_status: "SCHEDULED" })],
      }),
    });
    renderPage();

    const section = await findSection("Recent Releases");
    expect(within(section).getByText("Scheduled", { selector: "span" })).toBeInTheDocument();
  });
});

describe("semantics: no publication or data-availability claims", () => {
  const FORBIDDEN_WORDS = /\b(released|published|refreshed)\b/i;
  const FORBIDDEN_PHRASES = [/data is now available/i, /data.{0,20}available/i, /new data/i, /analysis refreshed/i, /\bupdated\b/i];

  it("never renders forbidden publication/availability language in the always-visible product copy", async () => {
    // The required disclosure text (see pages/Releases.tsx) legitimately
    // contains the word "published" -- but only as a negation ("do not
    // confirm ... has been published"), never as a claim. Excluding
    // that one sanctioned sentence proves nothing ELSE in the
    // always-visible copy (badges, headings, row text) uses this
    // language. Explanation panels (progressive disclosure, opened via
    // ExplanationTrigger's <details>) are excluded here -- their
    // curated educational copy legitimately discusses "published" (e.g.
    // PAST_DUE's own negation, or describing what a release generally
    // is) and is checked precisely by its own dedicated exact-string
    // tests, not by this page-wide word scan.
    resolveBoth({
      upcoming: buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem({ schedule_status: "SCHEDULED" })] }),
      recent: buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem({ schedule_status: "PAST_DUE" })] }),
    });
    renderPage();

    await screen.findByRole("heading", { name: "Upcoming Releases" });
    const disclosure = screen.getByText(/Release dates indicate scheduled publication dates/);

    const clone = document.body.cloneNode(true) as HTMLElement;
    clone.querySelectorAll("details").forEach((details) => details.remove());
    const bodyText = clone.textContent ?? "";
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

describe("explanations (Increment #17C)", () => {
  it("offers an 'Economic release' explanation next to the page title", async () => {
    resolveBoth();
    renderPage();

    await screen.findByRole("heading", { name: "Upcoming Releases" });
    const user = userEvent.setup();
    await user.click(screen.getByLabelText("What does Economic release mean?"));

    expect(screen.getByText(/scheduled publication of official economic data/i)).toBeInTheDocument();
  });

  it("offers a 'Scheduled date' explanation naming FRED as the source", async () => {
    resolveBoth();
    renderPage();

    const section = await findSection("Upcoming Releases");
    const user = userEvent.setup();
    await user.click(within(section).getByLabelText("What does Scheduled date mean?"));

    expect(within(section).getByText("Source: FRED release calendar")).toBeInTheDocument();
  });

  it("opens a curated explanation for each of the six curated V1 release types, keyed by provider_release_id", async () => {
    const curated: ReadonlyArray<[string, string, RegExp]> = [
      ["10", "Consumer Price Index (CPI)", /bureau of labor statistics|prices/i],
      ["54", "Personal Income and Outlays", /pce price index/i],
      ["50", "Employment Situation", /labor|employment|payroll/i],
      ["192", "Job Openings and Labor Turnover Survey (JOLTS)", /job openings|turnover/i],
      ["53", "Gross Domestic Product (GDP)", /goods and services|economic activity/i],
      ["9", "Advance Monthly Sales for Retail and Food Services", /early estimate/i],
    ];

    for (const [providerReleaseId, title, expectedDefinitionPattern] of curated) {
      resolveBoth({
        upcoming: buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem({ provider_release_id: providerReleaseId, name: title })] }),
      });
      const { unmount } = renderPage();

      const section = await findSection("Upcoming Releases");
      const user = userEvent.setup();
      const trigger = within(section).getByLabelText(`What does ${title} mean?`);
      await user.click(trigger);

      // Scoped to the opened panel itself and matched against its
      // combined text (not `getByText`, since the panel's title,
      // definition, and why-it-matters paragraphs can each legitimately
      // contain some of the same words the pattern looks for).
      const panel = trigger.closest("details") as HTMLDetailsElement;
      expect(panel.textContent ?? "").toMatch(expectedDefinitionPattern);

      unmount();
    }
  });

  it("shows no release-type explanation trigger for a release outside the curated V1 set", async () => {
    resolveBoth({
      upcoming: buildReleaseListResponse({
        releases: [buildReleaseOccurrenceItem({ provider_release_id: "999", name: "Some Future Release" })],
      }),
    });
    renderPage();

    await screen.findByText("Some Future Release");
    expect(screen.queryByLabelText("What does Some Future Release mean?")).not.toBeInTheDocument();
  });

  it("opens the SCHEDULED status explanation, and it never claims a time of day", async () => {
    resolveBoth({
      upcoming: buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem({ schedule_status: "SCHEDULED" })] }),
    });
    renderPage();

    const section = await findSection("Upcoming Releases");
    const user = userEvent.setup();
    await user.click(within(section).getByLabelText("What does Scheduled mean?"));

    const panelText = within(section).getByText(
      "The release is scheduled for this date according to Economic Intelligence's persisted release calendar.",
    );
    expect(panelText).toBeInTheDocument();
    expect(panelText.textContent).not.toMatch(/\d{1,2}:\d{2}\s*(am|pm)?/i);
  });

  it("opens the PAST_DUE status explanation, and it explicitly does not claim publication", async () => {
    resolveBoth({
      recent: buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem({ schedule_status: "PAST_DUE" })] }),
    });
    renderPage();

    const section = await findSection("Recent Releases");
    const user = userEvent.setup();
    await user.click(within(section).getByLabelText("What does Past due mean?"));

    expect(
      within(section).getByText(
        "The scheduled release date has passed. This status does not confirm that new data has been published, ingested, or incorporated into Economic Intelligence analysis.",
      ),
    ).toBeInTheDocument();
  });

  it("removing/disabling explanation triggers would leave the canonical schedule_status text on the page unchanged (explanations are additive, not load-bearing)", async () => {
    resolveBoth({
      upcoming: buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem({ schedule_status: "SCHEDULED" })] }),
    });
    renderPage();

    const section = await findSection("Upcoming Releases");
    // The canonical status Badge text is present and correct without
    // ever opening any explanation trigger -- explanations are a
    // read-more layer alongside it, not a dependency of it.
    expect(within(section).getByText("Scheduled", { selector: "span" })).toBeInTheDocument();
  });
});
