import { afterEach, describe, expect, it, vi } from "vitest";

import { getSinceLastVisit } from "./sinceLastVisit";
import { buildSinceLastVisitResponse } from "../test/fixtures/sinceLastVisit";

describe("getSinceLastVisit", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function stubFetch() {
    const fetchMock = vi.fn(
      async (_url: string, _init?: RequestInit) =>
        new Response(JSON.stringify(buildSinceLastVisitResponse()), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  it("calls GET /api/v1/since-last-visit with no query string when after is omitted", async () => {
    const fetchMock = stubFetch();
    await getSinceLastVisit();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/since-last-visit", expect.objectContaining({ method: "GET" }));
  });

  it("calls with no query string when after is explicitly null", async () => {
    const fetchMock = stubFetch();
    await getSinceLastVisit(null);
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/since-last-visit", expect.objectContaining({ method: "GET" }));
  });

  it("includes the exact after value, verbatim, as a query parameter -- never a value it computed itself", async () => {
    const fetchMock = stubFetch();
    await getSinceLastVisit("2026-09-10T14:30:00Z");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/since-last-visit?after=2026-09-10T14%3A30%3A00Z",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("only ever issues a GET request, never a mutating method", async () => {
    const fetchMock = stubFetch();
    await getSinceLastVisit();
    const call = fetchMock.mock.calls[0];
    if (!call) throw new Error("fetch was never called");
    const [, init] = call as [string, RequestInit];
    expect(init.method).toBe("GET");
  });

  it("resolves with the parsed JSON body", async () => {
    stubFetch();
    const result = await getSinceLastVisit();
    expect(result.first_visit).toBe(false);
    expect(result.inflation.monitor).toBe("inflation");
    expect(result.labor.monitor).toBe("labor");
  });
});
