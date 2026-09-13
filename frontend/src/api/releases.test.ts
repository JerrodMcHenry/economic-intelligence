import { afterEach, describe, expect, it, vi } from "vitest";

import { getReleases } from "./releases";

describe("getReleases", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function stubFetch() {
    const fetchMock = vi.fn(
      async (_url: string, _init?: RequestInit) =>
        new Response(JSON.stringify({ releases: [], pagination: { limit: 100, offset: 0, returned: 0, total: 0 } }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  function firstCall(fetchMock: ReturnType<typeof stubFetch>): [string, RequestInit] {
    const call = fetchMock.mock.calls[0];
    if (!call) throw new Error("fetch was never called");
    return call as [string, RequestInit];
  }

  it("calls GET /api/v1/releases with no query string when no params are given", async () => {
    const fetchMock = stubFetch();
    await getReleases();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/releases", expect.objectContaining({ method: "GET" }));
  });

  it("builds the exact query string the backend contract expects", async () => {
    const fetchMock = stubFetch();
    await getReleases({ start_date: "2026-09-13", end_date: "2026-10-28", limit: 100, offset: 0, order: "asc" });
    const [url] = firstCall(fetchMock);
    const params = new URLSearchParams(url.split("?")[1]);
    expect(params.get("start_date")).toBe("2026-09-13");
    expect(params.get("end_date")).toBe("2026-10-28");
    expect(params.get("limit")).toBe("100");
    expect(params.get("offset")).toBe("0");
    expect(params.get("order")).toBe("asc");
  });

  it("never calls the sync endpoint", async () => {
    const fetchMock = stubFetch();
    await getReleases({ start_date: "2026-09-13" });
    const [url] = firstCall(fetchMock);
    expect(url).not.toContain("/sync");
  });

  it("only ever issues a GET request, never a mutating method", async () => {
    const fetchMock = stubFetch();
    await getReleases();
    const [, init] = firstCall(fetchMock);
    expect(init.method).toBe("GET");
  });
});
