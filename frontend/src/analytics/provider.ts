/**
 * The analytics provider boundary (Increment #37).
 *
 * Exactly one module in the application knows which analytics service,
 * if any, receives an event. Components import `track` from
 * `src/analytics`; they never see a provider, a vendor SDK, a site id
 * or a transport. Swapping providers -- or removing analytics entirely
 * -- touches this file and nothing else.
 *
 * DISABLED IS THE DEFAULT. With no `VITE_ANALYTICS_PROVIDER`
 * configured, `resolveProvider()` returns the no-op and MacroChipz
 * behaves exactly as it does today. That is deliberate: as of #37 no
 * provider has been selected, because doing so responsibly requires a
 * human decision about cost and hosting (see
 * docs/architecture/product-measurement.md). Shipping the abstraction
 * without inventing a dependency is the point of this increment.
 */

/**
 * A provider receives an already-validated, already-allowlisted event.
 *
 * `send` is deliberately synchronous and returns `void`: fire and
 * forget. A provider doing network I/O owns its own asynchrony AND its
 * own failure -- it must never return a promise that could reject
 * unobserved. `track()` additionally wraps every call in a try/catch,
 * so a provider that throws synchronously cannot reach the product.
 */
export interface AnalyticsProvider {
  readonly name: string;
  send(event: string, properties: Readonly<Record<string, string | number | boolean>>): void;
}

/** Does nothing, successfully. The default, and what tests always get. */
export const noopProvider: AnalyticsProvider = {
  name: "noop",
  send() {
    // Intentionally empty. Analytics being disabled is a normal,
    // fully-supported state -- not a degraded one.
  },
};

/**
 * Prints events to the console. Local development only, opt-in via
 * `VITE_ANALYTICS_PROVIDER=debug`.
 *
 * It logs the event name and the allowlisted properties -- which, by
 * construction, are the only things `track()` would have sent to a
 * real provider. There is nothing here that we decided not to retain,
 * because the filtering happens before the provider is called.
 */
export const debugProvider: AnalyticsProvider = {
  name: "debug",
  send(event, properties) {
    // The one deliberate `console` call in application code. It exists
    // so a developer can see the vocabulary working locally without
    // configuring an external service, and it is unreachable in a
    // production build (see `resolveProvider`).
    console.info("[analytics]", event, properties);
  },
};

/**
 * Resolves the active provider from the build-time environment.
 *
 * Three rules, in order of precedence:
 *
 * 1. TEST always gets the no-op, regardless of configuration. A test
 *    run must never be able to reach a real analytics service, and
 *    this is enforced here rather than left to each test's discipline.
 * 2. `debug` is refused in a production build. A production bundle
 *    must not ship a console logger even if the variable is set by
 *    mistake.
 * 3. Anything unrecognised -- including unset, empty, or a provider
 *    name we do not implement -- resolves to the no-op. Analytics
 *    fails closed, and misconfiguration degrades to silence rather
 *    than to an error.
 */
export function resolveProvider(
  env: { MODE?: string; PROD?: boolean; VITE_ANALYTICS_PROVIDER?: string } = import.meta.env,
): AnalyticsProvider {
  if (env.MODE === "test") return noopProvider;

  const configured = (env.VITE_ANALYTICS_PROVIDER ?? "").trim().toLowerCase();
  if (configured === "debug" && env.PROD !== true) return debugProvider;

  return noopProvider;
}
