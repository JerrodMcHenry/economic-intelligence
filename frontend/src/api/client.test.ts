import { afterEach, describe, expect, it, vi } from "vitest";

import { apiGet } from "./client";
import { ApiError, isApiError } from "./errors";

describe("apiGet", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("parses a successful JSON response", async () => {
    const fixture = { hello: "world", count: 3 };
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify(fixture), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiGet<{ hello: string; count: number }>("/api/v1/example");

    expect(result).toEqual(fixture);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/example",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("does not treat a successful economic-data response as an infrastructure error", async () => {
    // Exactly the shape a canonical backend response can legitimately
    // take -- a 200 with a nested "unavailable" economic state. This
    // must parse normally, never throw ApiError.
    const fixture = { state: "INSUFFICIENT_DATA", comparison_available: false };
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify(fixture), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );

    const result = await apiGet<typeof fixture>("/api/v1/example");
    expect(result.state).toBe("INSUFFICIENT_DATA");
    expect(result.comparison_available).toBe(false);
  });

  it("raises ApiError with kind 'http' on a non-2xx response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "Database is currently unavailable." }), { status: 503 })),
    );

    await expect(apiGet("/api/v1/example")).rejects.toMatchObject({
      name: "ApiError",
      kind: "http",
      status: 503,
    });
  });

  it("raises ApiError with kind 'network' when fetch itself throws", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );

    let caught: unknown;
    try {
      await apiGet("/api/v1/example");
    } catch (error) {
      caught = error;
    }

    expect(isApiError(caught)).toBe(true);
    expect((caught as ApiError).kind).toBe("network");
  });

  it("never retries and never swallows an error", async () => {
    const fetchMock = vi.fn(async () => new Response("Internal Server Error", { status: 500 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiGet("/api/v1/example")).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
