import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchReleaseProcessingStatus } from "./processingStatus";

describe("fetchReleaseProcessingStatus", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function stubFetch() {
    const fetchMock = vi.fn(
      async (_url: string, _init?: RequestInit) =>
        new Response(JSON.stringify({ occurrences: [], pagination: { limit: 20, offset: 0, returned: 0, total: 0 } }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  it("calls GET /api/v1/releases/processing-status with no query string", async () => {
    const fetchMock = stubFetch();
    await fetchReleaseProcessingStatus();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/releases/processing-status",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("only ever issues a GET request, never a mutating method", async () => {
    const fetchMock = stubFetch();
    await fetchReleaseProcessingStatus();
    const call = fetchMock.mock.calls[0];
    if (!call) throw new Error("fetch was never called");
    const [, init] = call as [string, RequestInit];
    expect(init.method).toBe("GET");
  });

  it("never references any mutating/process path", async () => {
    const fetchMock = stubFetch();
    await fetchReleaseProcessingStatus();
    const call = fetchMock.mock.calls[0];
    if (!call) throw new Error("fetch was never called");
    const [url] = call as [string, RequestInit];
    expect(url).not.toMatch(/\/sync\b/);
    expect(url).not.toMatch(/\/process\b/);
  });
});
