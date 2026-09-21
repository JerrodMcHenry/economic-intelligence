/**
 * Route-level instrumentation, including the two privacy rules that
 * live in `usePageViewed` rather than in the caller: pathnames are
 * normalized to known templates, and referrers are reduced to a class.
 */
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { AnalyticsProvider } from "./provider";
import { track, __setProviderForTests } from "./track";
import { classifyReferrer, normalizeRoute, usePageViewed } from "./usePageViewed";

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

function recordingProvider(sent: Recorded[]): AnalyticsProvider {
  return {
    name: "recording",
    send(event, properties) {
      sent.push({ event, properties: { ...properties } });
    },
  };
}

function Harness() {
  usePageViewed();
  return <p>content</p>;
}

function renderAt(path: string, sent: Recorded[]) {
  __setProviderForTests(recordingProvider(sent));
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="*" element={<Harness />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  __setProviderForTests(null);
});

describe("normalizeRoute", () => {
  it("passes through every known route template", () => {
    for (const route of ["/", "/overview", "/inflation", "/labor", "/rates", "/releases"]) {
      expect(normalizeRoute(route)).toBe(route);
    }
  });

  it("tolerates a trailing slash", () => {
    expect(normalizeRoute("/rates/")).toBe("/rates");
  });

  it("collapses anything unknown to unknown_route rather than forwarding it", () => {
    // This is the rule that stops `page_viewed` becoming a way to send
    // whatever is in the address bar.
    expect(normalizeRoute("/not-a-page")).toBe("unknown_route");
    expect(normalizeRoute("/inflation/secret-id")).toBe("unknown_route");
    expect(normalizeRoute("/reset?token=abc123")).toBe("unknown_route");
    expect(normalizeRoute("/%2e%2e/etc/passwd")).toBe("unknown_route");
  });
});

describe("classifyReferrer", () => {
  it("reports no referrer as none", () => {
    expect(classifyReferrer("", "https://macrochipz.test")).toBe("none");
  });

  it("distinguishes internal from external without keeping the URL", () => {
    expect(classifyReferrer("https://macrochipz.test/inflation", "https://macrochipz.test")).toBe("internal");
    expect(classifyReferrer("https://example.com/somewhere?q=private", "https://macrochipz.test")).toBe("external");
  });

  it("treats an unparseable referrer as none", () => {
    expect(classifyReferrer("not a url", "https://macrochipz.test")).toBe("none");
  });
});

describe("usePageViewed", () => {
  it("emits page_viewed once for a non-world route", () => {
    const sent: Recorded[] = [];
    renderAt("/releases", sent);

    expect(sent).toHaveLength(1);
    expect(at(sent, 0).event).toBe("page_viewed");
    expect(at(sent, 0).properties.route_template).toBe("/releases");
  });

  it("emits page_viewed and world_opened for a world route", () => {
    const sent: Recorded[] = [];
    renderAt("/inflation", sent);

    expect(sent.map((record) => record.event)).toEqual(["page_viewed", "world_opened"]);
    expect(at(sent, 1).properties).toEqual({ world: "inflation" });
  });

  it("does not emit world_opened for the homepage", () => {
    const sent: Recorded[] = [];
    renderAt("/", sent);

    expect(sent.map((record) => record.event)).toEqual(["page_viewed"]);
  });

  it("reports an unknown path as unknown_route and never as the raw path", () => {
    const sent: Recorded[] = [];
    renderAt("/leaky-path?token=sensitive", sent);

    expect(at(sent, 0).properties.route_template).toBe("unknown_route");
    expect(JSON.stringify(at(sent, 0).properties)).not.toContain("sensitive");
    expect(JSON.stringify(at(sent, 0).properties)).not.toContain("leaky-path");
  });

  it("does not double-count when the component re-renders on the same route", () => {
    const sent: Recorded[] = [];
    const { rerender } = renderAt("/rates", sent);
    rerender(
      <MemoryRouter initialEntries={["/rates"]}>
        <Routes>
          <Route path="*" element={<Harness />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(sent.filter((record) => record.event === "page_viewed")).toHaveLength(1);
  });

  it("renders its content normally when analytics throws", () => {
    __setProviderForTests({
      name: "exploding",
      send() {
        throw new Error("blocked");
      },
    });

    const { getByText } = render(
      <MemoryRouter initialEntries={["/inflation"]}>
        <Routes>
          <Route path="*" element={<Harness />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(getByText("content")).toBeInTheDocument();
  });

  it("renders its content normally when analytics is disabled", () => {
    __setProviderForTests(null);

    const { getByText } = render(
      <MemoryRouter initialEntries={["/inflation"]}>
        <Routes>
          <Route path="*" element={<Harness />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(getByText("content")).toBeInTheDocument();
    // And the module-level `track` is still callable without a provider.
    expect(() => track("world_opened", { world: "rates" })).not.toThrow();
  });
});
