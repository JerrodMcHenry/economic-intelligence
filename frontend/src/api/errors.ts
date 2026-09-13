/**
 * Frontend infrastructure error model.
 *
 * Distinguishes exactly two failure kinds the API client can raise:
 *
 * - "network": the request never reached the server (offline, DNS,
 *   connection refused, CORS rejection, etc.).
 * - "http": the server responded, but with a non-2xx status
 *   (typically a backend infrastructure failure -- 503 "Database is
 *   currently unavailable", 500 "Database error...", per the
 *   backend's own documented convention in
 *   docs/methodology/inflation-monitor-v1.0.md's "Infrastructure
 *   failure vs. economic insufficiency").
 *
 * `ApiError` is deliberately NOT used for economic-data states. A
 * canonical backend response with `state: "INSUFFICIENT_DATA"`,
 * `relationship: "UNAVAILABLE"`, or `comparison_available: false` is a
 * normal, successful HTTP 200 response -- it must never be converted
 * into an `ApiError`. That distinction is what callers are expected to
 * make themselves, using the parsed response body's own fields; this
 * module only ever concerns itself with whether the HTTP exchange
 * itself succeeded.
 */

export type ApiErrorKind = "network" | "http";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;

  constructor(kind: ApiErrorKind, message: string, status?: number, options?: ErrorOptions) {
    super(message, options);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}
