import { beforeEach, describe, expect, it, vi } from "vitest";

import { readSinceLastVisitCheckpoint, writeSinceLastVisitCheckpoint } from "./sinceLastVisitCheckpoint";

const STORAGE_KEY = "economic-intelligence:since-last-visit:v1";

beforeEach(() => {
  window.localStorage.clear();
});

describe("readSinceLastVisitCheckpoint", () => {
  it("returns null when no checkpoint is stored (first visit)", () => {
    expect(readSinceLastVisitCheckpoint()).toBeNull();
  });

  it("returns the stored checkpoint when it is well-formed", () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ schemaVersion: 1, through: "2026-09-10T14:30:00Z" }));
    expect(readSinceLastVisitCheckpoint()).toEqual({ schemaVersion: 1, through: "2026-09-10T14:30:00Z" });
  });

  it("degrades to null (never throws) for malformed JSON", () => {
    window.localStorage.setItem(STORAGE_KEY, "{not valid json");
    expect(readSinceLastVisitCheckpoint()).toBeNull();
  });

  it("degrades to null for a wrong schemaVersion (a future, incompatible shape)", () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ schemaVersion: 2, through: "2026-09-10T14:30:00Z" }));
    expect(readSinceLastVisitCheckpoint()).toBeNull();
  });

  it("degrades to null when through is missing", () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ schemaVersion: 1 }));
    expect(readSinceLastVisitCheckpoint()).toBeNull();
  });

  it("degrades to null when through is an empty string", () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ schemaVersion: 1, through: "" }));
    expect(readSinceLastVisitCheckpoint()).toBeNull();
  });

  it("degrades to null when through is not a real, parseable timestamp", () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ schemaVersion: 1, through: "not-a-real-date" }));
    expect(readSinceLastVisitCheckpoint()).toBeNull();
  });

  it("degrades to null when the stored value is a JSON array, not an object", () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(["a", "b"]));
    expect(readSinceLastVisitCheckpoint()).toBeNull();
  });

  it("degrades to null when the stored value is a bare JSON string", () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify("2026-09-10T14:30:00Z"));
    expect(readSinceLastVisitCheckpoint()).toBeNull();
  });

  it("degrades to null (never throws) when localStorage.getItem itself throws", () => {
    const spy = vi.spyOn(window.localStorage.__proto__, "getItem").mockImplementation(() => {
      throw new Error("SecurityError: storage disabled");
    });
    try {
      expect(readSinceLastVisitCheckpoint()).toBeNull();
    } finally {
      spy.mockRestore();
    }
  });
});

describe("writeSinceLastVisitCheckpoint", () => {
  it("persists the exact value handed to it, verbatim, under the stable storage key", () => {
    writeSinceLastVisitCheckpoint("2026-09-15T09:00:00Z");
    const raw = window.localStorage.getItem(STORAGE_KEY);
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw as string)).toEqual({ schemaVersion: 1, through: "2026-09-15T09:00:00Z" });
  });

  it("a subsequent read round-trips the exact written value", () => {
    writeSinceLastVisitCheckpoint("2026-09-15T09:00:00Z");
    expect(readSinceLastVisitCheckpoint()).toEqual({ schemaVersion: 1, through: "2026-09-15T09:00:00Z" });
  });

  it("overwrites a previously stored checkpoint (last write wins, contract §14)", () => {
    writeSinceLastVisitCheckpoint("2026-09-10T00:00:00Z");
    writeSinceLastVisitCheckpoint("2026-09-15T00:00:00Z");
    expect(readSinceLastVisitCheckpoint()).toEqual({ schemaVersion: 1, through: "2026-09-15T00:00:00Z" });
  });

  it("does not throw (silently no-ops) when localStorage.setItem itself throws", () => {
    const spy = vi.spyOn(window.localStorage.__proto__, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    try {
      expect(() => writeSinceLastVisitCheckpoint("2026-09-15T09:00:00Z")).not.toThrow();
    } finally {
      spy.mockRestore();
    }
  });
});
