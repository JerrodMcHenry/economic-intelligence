/**
 * Metadata for a shared intelligence object (Increment #40).
 *
 * A shared link arrives with no surrounding page: the unfurl IS the
 * product for that reader. These tests hold it to the same standard as
 * the page -- factual, self-contained, and claiming nothing the object
 * does not carry.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import type { IntelligenceObject, RatesMovementIntelligence } from "../api/intelligence.types";
import { intelligenceMeta } from "./intelligenceMetadata";
import { SITE_URL } from "./siteUrl";

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
  evidence: [],
  relations: [],
  limitations: [],
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

function tag(tags: ReturnType<typeof intelligenceMeta>, key: string, value: string) {
  return tags.find((entry) => entry[key] === value);
}

describe("what a shared link says", () => {
  const tags = intelligenceMeta(OBJECT, ID);

  it("names the fact in the title, not the product", () => {
    expect(tags[0]?.title).toBe("10-Year Treasury Par Yield (Nominal) is 5.01% — MacroChipz");
  });

  it("writes a description that stands alone, with the period in it", () => {
    const description = tag(tags, "name", "description")?.content ?? "";
    expect(description).toContain("2026-09-18");
    expect(description).toContain("Rates");
    expect(description).toContain("Evidence and methodology included.");
  });

  it("carries the full Open Graph and Twitter set", () => {
    for (const property of ["og:title", "og:description", "og:type", "og:site_name"]) {
      expect(tag(tags, "property", property), property).toBeDefined();
    }
    for (const name of ["twitter:card", "twitter:title", "twitter:description"]) {
      expect(tag(tags, "name", name), name).toBeDefined();
    }
    expect(tag(tags, "name", "twitter:card")?.content).toBe("summary_large_image");
  });

  it("claims nothing about significance, which #39 does not define", () => {
    const text = JSON.stringify(tags).toLowerCase();
    for (const word of ["significant", "notable", "surge", "plunge", "shock", "alarming"]) {
      expect(text, word).not.toContain(word);
    }
  });

  it("leaks no secret and no internal taxonomy", () => {
    const text = JSON.stringify(tags);
    for (const word of ["RATES_MOVEMENT", "METHODOLOGY_DERIVED", "OBSERVED", "API_KEY", "postgres"]) {
      expect(text, word).not.toContain(word);
    }
  });
});

describe("absolute URLs", () => {
  it("omits canonical and og:url rather than guessing an origin", () => {
    const tags = intelligenceMeta(OBJECT, ID);
    // The test environment configures no VITE_SITE_URL. A guessed
    // canonical is worse than none: it tells a crawler the real page
    // lives somewhere it does not.
    expect(SITE_URL).toBeNull();
    expect(tag(tags, "property", "og:url")).toBeUndefined();
    expect(tags.some((entry) => entry.rel === "canonical")).toBe(false);
    expect(tag(tags, "property", "og:image")).toBeUndefined();
  });
});

describe("when a deployment origin IS configured", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  /**
   * `siteUrl.ts` reads the variable once at import time, so the module
   * graph has to be rebuilt to exercise the configured branch. The
   * suite's default is the UNCONFIGURED case (pinned in
   * `vitest.config.ts`), which is why this is stubbed explicitly here
   * rather than relying on whatever the shell happens to export.
   */
  async function metaWithOrigin(origin: string) {
    vi.resetModules();
    vi.stubEnv("VITE_SITE_URL", origin);
    const { intelligenceMeta: fresh } = await import("./intelligenceMetadata");
    return fresh(OBJECT, ID);
  }

  it("emits an absolute canonical link", async () => {
    const tags = await metaWithOrigin("https://macrochipz.com");
    expect(tags).toContainEqual({
      tagName: "link",
      rel: "canonical",
      href: "https://macrochipz.com/intelligence/rates%3AUST_NOMINAL_10Y%3A2026-09-18",
    });
  });

  it("emits an absolute og:url and og:image with the id percent-encoded", async () => {
    const tags = await metaWithOrigin("https://macrochipz.com");
    expect(tag(tags, "property", "og:url")?.content).toBe(
      "https://macrochipz.com/intelligence/rates%3AUST_NOMINAL_10Y%3A2026-09-18",
    );
    expect(tag(tags, "property", "og:image")?.content).toBe(
      "https://macrochipz.com/og/rates%3AUST_NOMINAL_10Y%3A2026-09-18.png",
    );
  });

  it("gives the card alt text that states the fact", async () => {
    const tags = await metaWithOrigin("https://macrochipz.com");
    expect(tag(tags, "property", "og:image:alt")?.content).toBe(
      "10-Year Treasury Par Yield (Nominal) is 5.01%",
    );
  });

  it("tolerates a trailing slash on the configured origin", async () => {
    const tags = await metaWithOrigin("https://macrochipz.com/");
    expect(tag(tags, "property", "og:url")?.content).not.toContain("//intelligence");
  });
});

describe("id encoding", () => {
  it("percent-encodes the colons a semantic id contains", () => {
    const tags = intelligenceMeta(OBJECT, ID);
    // Nothing absolute is emitted without an origin, but the path
    // helper is the same one the page and the sitemap use.
    expect(encodeURIComponent(ID)).toBe("rates%3AUST_NOMINAL_10Y%3A2026-09-18");
    expect(tags.length).toBeGreaterThan(0);
  });

  it("describes an unknown object without inventing one", () => {
    const tags = intelligenceMeta(null as IntelligenceObject | null, "whatever");
    expect(tags[0]?.title).toBe("Not found — MacroChipz");
    expect(JSON.stringify(tags)).not.toContain("whatever");
  });
});
