/**
 * Open Graph card generation (Increment #40).
 *
 * The card is the only thing many people will ever see of an object.
 * These tests hold it to the page's standard: composed from structured
 * facts, byte-identical for identical facts, and never fabricated when
 * the facts are missing.
 */
import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";

import { compose, loadFont, render } from "./generate-og-images.mjs";

const RATES = {
  id: "rates:UST_NOMINAL_10Y:2026-09-18",
  type: "RATES_MOVEMENT",
  world: "rates",
  effective_period: "2026-09-18",
  payload: {
    series_title: "10-Year Treasury Par Yield (Nominal)",
    latest_value: 5.01,
    changes: [
      { window: "1_SESSION", available: true, change_basis_points: 7 },
      { window: "21_SESSIONS", available: true, change_basis_points: 36 },
      { window: "63_SESSIONS", available: false, change_basis_points: null },
    ],
  },
};

describe("composing a card", () => {
  it("states the fact, from the object's own numbers", () => {
    const content = compose(RATES);
    expect(content.headline).toBe("10-Year Treasury Par Yield (Nominal) is 5.01%");
    expect(content.eyebrow).toBe("RATES");
    expect(content.footer).toBe("2026-09-18");
  });

  it("shows only the change windows the object says are available", () => {
    const content = compose(RATES);
    expect(content.figures).toEqual([
      { label: "1 session", value: "+7 bp" },
      { label: "21 sessions", value: "+36 bp" },
    ]);
  });

  it("skips an object rather than publishing a misleading card", () => {
    expect(compose({ ...RATES, payload: { ...RATES.payload, latest_value: null } })).toBeNull();
    expect(compose({ ...RATES, payload: { ...RATES.payload, series_title: "" } })).toBeNull();
  });

  it("falls back to a truthful, less specific card for other types", () => {
    const content = compose({ id: "release:CPI:2026-09-11", type: "RELEASE_PROCESSED", world: "inflation" });
    expect(content).not.toBeNull();
    expect(content.figures).toEqual([]);
    expect(content.eyebrow).toBe("INFLATION");
  });

  it("recomputes nothing — the basis points come straight off the object", () => {
    const content = compose({
      ...RATES,
      payload: { ...RATES.payload, changes: [{ window: "1_SESSION", available: true, change_basis_points: -12 }] },
    });
    expect(content.figures[0].value).toBe("−12 bp");
  });
});

describe("determinism", () => {
  it("produces byte-identical PNGs for identical facts", async () => {
    const font = loadFont();
    const content = compose(RATES);
    const [first, second] = await Promise.all([render(content, font), render(content, font)]);
    const digest = (buffer) => createHash("sha256").update(buffer).digest("hex");
    expect(digest(first)).toBe(digest(second));
  }, 30_000);

  it("produces a different card when the facts differ", async () => {
    const font = loadFont();
    const a = await render(compose(RATES), font);
    const b = await render(compose({ ...RATES, payload: { ...RATES.payload, latest_value: 4.12 } }), font);
    expect(Buffer.compare(a, b)).not.toBe(0);
  }, 30_000);
});

describe("secrets", () => {
  it("puts nothing on the card that is not a published fact", () => {
    const content = compose(RATES);
    const text = JSON.stringify(content);
    for (const word of ["API_KEY", "postgres", "password", "token", "RATES_MOVEMENT"]) {
      expect(text, word).not.toContain(word);
    }
  });
});
