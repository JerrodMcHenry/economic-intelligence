/**
 * Minimal, typed fetch wrapper for the FastAPI backend.
 *
 * Responsibilities, and only these: resolve the configured base URL,
 * issue the request, verify HTTP success, and parse the JSON body.
 * This module has zero knowledge of what any endpoint's response
 * means economically -- it never inspects `state`, `relationship`,
 * `comparison_available`, or any other domain field. That parsing and
 * interpretation belongs entirely to callers, using their own typed
 * response shapes (see the Inflation Monitor UI, #16B, for the first
 * such caller).
 *
 * In local development, `VITE_API_BASE_URL` is left unset, so
 * requests use relative paths (e.g. `/api/v1/monitors/inflation`)
 * against the current origin -- the Vite dev server proxies `/api` to
 * the local FastAPI backend (see vite.config.ts). In production,
 * `VITE_API_BASE_URL` is set at build time to the deployed API's
 * origin. Everything prefixed `VITE_` is bundled into client-side
 * JavaScript and is publicly visible in the browser -- this is
 * configuration, never a secret (see frontend/.env.example).
 */

import { ApiError } from "./errors";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

/**
 * Issue a GET request and parse its JSON body.
 *
 * Throws `ApiError` for a network failure or a non-2xx HTTP status.
 * Never retries, never swallows an error, and never converts a
 * successful (2xx) response into an error, regardless of what its
 * body contains -- a canonical economic-data-unavailable response is
 * still a successful response as far as this function is concerned.
 *
 * The `as T` at the JSON-parsing boundary below is the one place this
 * client narrows an inherently untyped payload (`fetch`'s `Response.json()`
 * itself returns `any`) into the shape the caller asked for; it is not
 * runtime-validated here. Callers own picking `T` correctly and, if a
 * response shape's correctness needs to be verified rather than
 * merely asserted, that validation belongs at the call site.
 */
export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      method: "GET",
      headers: { Accept: "application/json", ...init?.headers },
    });
  } catch (cause) {
    throw new ApiError("network", "Could not reach the server.", undefined, { cause });
  }

  if (!response.ok) {
    throw new ApiError("http", `Request failed with status ${response.status}.`, response.status);
  }

  return (await response.json()) as T;
}
