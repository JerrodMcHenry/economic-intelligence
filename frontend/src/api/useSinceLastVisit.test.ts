import { StrictMode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getSinceLastVisit } from "./sinceLastVisit";
import { useSinceLastVisit } from "./useSinceLastVisit";
import { readSinceLastVisitCheckpoint, writeSinceLastVisitCheckpoint } from "../lib/sinceLastVisitCheckpoint";
import { buildSinceLastVisitResponse } from "../test/fixtures/sinceLastVisit";

vi.mock("./sinceLastVisit", () => ({
  getSinceLastVisit: vi.fn(),
}));

const mockedGetSinceLastVisit = vi.mocked(getSinceLastVisit);

beforeEach(() => {
  mockedGetSinceLastVisit.mockReset();
  window.localStorage.clear();
});

describe("useSinceLastVisit", () => {
  it("starts in the loading state", () => {
    mockedGetSinceLastVisit.mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useSinceLastVisit());
    expect(result.current.status).toBe("loading");
  });

  it("first visit (no stored checkpoint): requests with no after value", async () => {
    mockedGetSinceLastVisit.mockResolvedValue(buildSinceLastVisitResponse({ first_visit: true }));
    renderHook(() => useSinceLastVisit());
    await waitFor(() => expect(mockedGetSinceLastVisit).toHaveBeenCalled());
    expect(mockedGetSinceLastVisit).toHaveBeenCalledWith(null);
  });

  it("return visit: requests with the exact stored checkpoint's through value", async () => {
    writeSinceLastVisitCheckpoint("2026-09-08T00:00:00Z");
    mockedGetSinceLastVisit.mockResolvedValue(buildSinceLastVisitResponse());
    renderHook(() => useSinceLastVisit());
    await waitFor(() => expect(mockedGetSinceLastVisit).toHaveBeenCalled());
    expect(mockedGetSinceLastVisit).toHaveBeenCalledWith("2026-09-08T00:00:00Z");
  });

  it("on success, transitions to the success state with the exact response data", async () => {
    const response = buildSinceLastVisitResponse();
    mockedGetSinceLastVisit.mockResolvedValue(response);
    const { result } = renderHook(() => useSinceLastVisit());
    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(result.current.status === "success" && result.current.data).toEqual(response);
  });

  it("on success, persists the response's OWN through value -- never a computed one", async () => {
    const response = buildSinceLastVisitResponse({ through: "2026-09-15T09:00:00Z" });
    mockedGetSinceLastVisit.mockResolvedValue(response);
    const { result } = renderHook(() => useSinceLastVisit());
    await waitFor(() => expect(result.current.status).toBe("success"));
    await waitFor(() => expect(readSinceLastVisitCheckpoint()?.through).toBe("2026-09-15T09:00:00Z"));
  });

  it("on API failure, transitions to the error state and NEVER writes a checkpoint (contract §91)", async () => {
    mockedGetSinceLastVisit.mockRejectedValue(new Error("network down"));
    const { result } = renderHook(() => useSinceLastVisit());
    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(readSinceLastVisitCheckpoint()).toBeNull();
  });

  it("reload() re-reads the checkpoint freshly and re-fetches with the newly-persisted through", async () => {
    mockedGetSinceLastVisit.mockResolvedValueOnce(buildSinceLastVisitResponse({ through: "2026-09-10T00:00:00Z" }));
    const { result } = renderHook(() => useSinceLastVisit());
    await waitFor(() => expect(result.current.status).toBe("success"));
    await waitFor(() => expect(readSinceLastVisitCheckpoint()?.through).toBe("2026-09-10T00:00:00Z"));

    mockedGetSinceLastVisit.mockResolvedValueOnce(buildSinceLastVisitResponse({ through: "2026-09-11T00:00:00Z" }));
    act(() => result.current.reload());
    await waitFor(() => expect(mockedGetSinceLastVisit).toHaveBeenLastCalledWith("2026-09-10T00:00:00Z"));
  });

  it("does not refetch merely because the checkpoint was written -- no reactive loop (contract §13)", async () => {
    mockedGetSinceLastVisit.mockResolvedValue(buildSinceLastVisitResponse());
    renderHook(() => useSinceLastVisit());
    await waitFor(() => expect(mockedGetSinceLastVisit).toHaveBeenCalledTimes(1));
    // Give any errant reactive effect a chance to fire, then confirm no second call happened.
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(mockedGetSinceLastVisit).toHaveBeenCalledTimes(1);
  });

  it("Strict Mode double-invocation does not double-fetch beyond the framework's own expected double-mount, and never corrupts the persisted checkpoint", async () => {
    const response = buildSinceLastVisitResponse({ through: "2026-09-15T09:00:00Z" });
    mockedGetSinceLastVisit.mockResolvedValue(response);
    const { result } = renderHook(() => useSinceLastVisit(), { wrapper: StrictMode });
    await waitFor(() => expect(result.current.status).toBe("success"));
    // Whatever the exact call count Strict Mode's own double-invocation
    // produces, the persisted value is exactly the response's own
    // through -- never a different, corrupted, or partially-written value.
    expect(readSinceLastVisitCheckpoint()).toEqual({ schemaVersion: 1, through: "2026-09-15T09:00:00Z" });
  });

  it("never reads the browser's own clock to construct a checkpoint value (contract §8/§89, hard requirement)", async () => {
    const dateNowSpy = vi.spyOn(Date, "now").mockReturnValue(0);
    try {
      const response = buildSinceLastVisitResponse({ through: "2026-09-15T09:00:00Z" });
      mockedGetSinceLastVisit.mockResolvedValue(response);
      const { result } = renderHook(() => useSinceLastVisit());
      await waitFor(() => expect(result.current.status).toBe("success"));
      await waitFor(() => expect(readSinceLastVisitCheckpoint()?.through).toBe("2026-09-15T09:00:00Z"));
      // A wrong Date.now() (year 1970) never leaks into the persisted value.
      expect(readSinceLastVisitCheckpoint()?.through).not.toContain("1970");
    } finally {
      dateNowSpy.mockRestore();
    }
  });
});
