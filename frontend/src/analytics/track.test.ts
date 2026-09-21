/**
 * Increment #37's core guarantees, tested directly.
 *
 * The three things that must be true of `track()` are that it never
 * throws, that it sends only allowlisted primitives, and that a test
 * run can never reach a real provider. Everything below exists to
 * prove one of those.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import { EVENT_PROPERTY_ALLOWLIST, ANALYTICS_EVENT_NAMES, type AnalyticsEventName } from "./events";
import { debugProvider, noopProvider, resolveProvider, type AnalyticsProvider } from "./provider";
import { track, __setProviderForTests } from "./track";

interface Recorded {
  event: string;
  properties: Record<string, string | number | boolean>;
}

/** Narrows away `noUncheckedIndexedAccess`'s `| undefined` with a useful failure. */
function at(records: ReadonlyArray<Recorded>, index: number): Recorded {
  const record = records[index];
  if (record === undefined) throw new Error(`expected an event at index ${index}, got ${records.length} events`);
  return record;
}

function recordingProvider(): { provider: AnalyticsProvider; sent: Recorded[] } {
  const sent: Recorded[] = [];
  return {
    sent,
    provider: {
      name: "recording",
      send(event, properties) {
        sent.push({ event, properties: { ...properties } });
      },
    },
  };
}

afterEach(() => {
  __setProviderForTests(null);
  vi.restoreAllMocks();
});

describe("provider resolution", () => {
  it("resolves to the no-op when nothing is configured -- disabled is the default", () => {
    expect(resolveProvider({ MODE: "production", PROD: true })).toBe(noopProvider);
    expect(resolveProvider({ MODE: "development", PROD: false, VITE_ANALYTICS_PROVIDER: "" })).toBe(noopProvider);
  });

  it("resolves to the no-op in test mode even when a provider is configured", () => {
    // A test run must not be able to reach a real analytics service,
    // and that is enforced here rather than left to each test file.
    expect(resolveProvider({ MODE: "test", PROD: false, VITE_ANALYTICS_PROVIDER: "debug" })).toBe(noopProvider);
    expect(resolveProvider({ MODE: "test", PROD: false, VITE_ANALYTICS_PROVIDER: "plausible" })).toBe(noopProvider);
  });

  it("allows the debug provider only outside a production build", () => {
    expect(resolveProvider({ MODE: "development", PROD: false, VITE_ANALYTICS_PROVIDER: "debug" })).toBe(debugProvider);
    expect(resolveProvider({ MODE: "production", PROD: true, VITE_ANALYTICS_PROVIDER: "debug" })).toBe(noopProvider);
  });

  it("degrades an unrecognised provider name to the no-op rather than erroring", () => {
    expect(resolveProvider({ MODE: "production", PROD: true, VITE_ANALYTICS_PROVIDER: "not-a-provider" })).toBe(
      noopProvider,
    );
  });

  it("uses the real Vite environment by default, which under Vitest is test mode", () => {
    // Proves the default argument is wired to import.meta.env and that
    // this suite is therefore running against the no-op.
    expect(resolveProvider()).toBe(noopProvider);
  });
});

describe("track", () => {
  it("sends a valid event with its allowlisted properties", () => {
    const { provider, sent } = recordingProvider();
    __setProviderForTests(provider);

    track("evidence_expanded", { object_type: "inflation_metric" });

    expect(sent).toEqual([{ event: "evidence_expanded", properties: { object_type: "inflation_metric" } }]);
  });

  it("drops properties that are not on the event's allowlist", () => {
    const { provider, sent } = recordingProvider();
    __setProviderForTests(provider);

    // Cast models a widened type or a dynamically assembled object --
    // the compiler would reject this spelling in product code.
    track("world_opened", {
      world: "inflation",
      question: "why is inflation high?",
      email: "someone@example.com",
    } as never);

    expect(sent).toHaveLength(1);
    expect(at(sent, 0).properties).toEqual({ world: "inflation" });
    expect(at(sent, 0).properties).not.toHaveProperty("question");
    expect(at(sent, 0).properties).not.toHaveProperty("email");
  });

  it("drops non-primitive values even for allowlisted keys", () => {
    const { provider, sent } = recordingProvider();
    __setProviderForTests(provider);

    track("explainer_opened", { explainer_id: { toString: () => "leaked" } } as never);
    track("explainer_opened", { explainer_id: ["leaked"] } as never);
    track("explainer_opened", { explainer_id: null } as never);
    track("explainer_opened", { explainer_id: undefined } as never);

    expect(sent).toHaveLength(4);
    for (const record of sent) expect(record.properties).toEqual({});
  });

  it("drops empty strings and non-finite numbers", () => {
    const { provider, sent } = recordingProvider();
    __setProviderForTests(provider);

    track("explainer_opened", { explainer_id: "" });
    track("empty_state_viewed", { surface: Number.NaN as never });

    expect(at(sent, 0).properties).toEqual({});
    expect(at(sent, 1).properties).toEqual({});
  });

  it("truncates an unexpectedly long string rather than forwarding it", () => {
    const { provider, sent } = recordingProvider();
    __setProviderForTests(provider);

    track("explainer_opened", { explainer_id: "x".repeat(500) });

    expect(String(at(sent, 0).properties.explainer_id)).toHaveLength(120);
  });

  it("ignores an event name that is not in the vocabulary", () => {
    const { provider, sent } = recordingProvider();
    __setProviderForTests(provider);

    track("definitely_not_an_event" as AnalyticsEventName, {} as never);

    expect(sent).toHaveLength(0);
  });

  it("never throws when the provider throws synchronously", () => {
    __setProviderForTests({
      name: "exploding",
      send() {
        throw new Error("blocked by an extension");
      },
    });

    // The product calls this inside click handlers and effects. If it
    // can throw, a blocked analytics request becomes a broken page.
    expect(() => track("world_opened", { world: "rates" })).not.toThrow();
  });

  it("never throws when the provider is malformed", () => {
    __setProviderForTests({ name: "broken" } as unknown as AnalyticsProvider);

    expect(() => track("world_opened", { world: "rates" })).not.toThrow();
  });

  it("produces no unhandled rejection when a provider returns a rejected promise", async () => {
    const unhandled = vi.fn();
    process.on("unhandledRejection", unhandled);
    __setProviderForTests({
      name: "async-failing",
      send() {
        // A provider that forgets to catch its own transport failure.
        void Promise.reject(new Error("network")).catch(() => {});
      },
    });

    track("world_opened", { world: "labor" });
    await new Promise((resolve) => setTimeout(resolve, 0));
    process.off("unhandledRejection", unhandled);

    expect(unhandled).not.toHaveBeenCalled();
  });

  it("returns void, so no caller can await it and block rendering", () => {
    __setProviderForTests(noopProvider);
    expect(track("world_opened", { world: "inflation" })).toBeUndefined();
  });

  it("is a silent no-op when analytics is disabled", () => {
    __setProviderForTests(noopProvider);
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const error = vi.spyOn(console, "error").mockImplementation(() => {});

    for (const name of ANALYTICS_EVENT_NAMES) {
      expect(() => track(name, { world: "inflation" } as never)).not.toThrow();
    }

    // A disabled provider is a normal, supported state -- not something
    // to complain about on every interaction.
    expect(warn).not.toHaveBeenCalled();
    expect(error).not.toHaveBeenCalled();
  });

  it("covers every event in the vocabulary with an allowlist entry", () => {
    for (const name of ANALYTICS_EVENT_NAMES) {
      expect(EVENT_PROPERTY_ALLOWLIST[name].length).toBeGreaterThan(0);
    }
  });
});
