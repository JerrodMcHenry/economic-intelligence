/**
 * `track()` -- the single call every component uses, and the only
 * place an event can become a provider call (Increment #37).
 *
 * Three guarantees this function makes, in the order they matter:
 *
 * 1. IT NEVER THROWS. Analytics is optional infrastructure. A failing,
 *    blocked, misconfigured or absent provider must be invisible to
 *    the reader, so every failure mode ends inside the try/catch here.
 *    Nothing awaits it, so no navigation or render can wait on it, and
 *    it returns `void` rather than a promise, so there is nothing that
 *    can reject unobserved.
 *
 * 2. IT SENDS ONLY ALLOWLISTED PROPERTIES. Values are filtered against
 *    `EVENT_PROPERTY_ALLOWLIST` and then checked to be primitives of
 *    bounded length. A caller cannot leak an object, a user's typed
 *    question, a URL or a stack trace through this API even by
 *    accident -- the type system would stop it first, and this stops
 *    it if a type is ever widened.
 *
 * 3. IT KNOWS NOTHING ABOUT ANY VENDOR. The provider is resolved once,
 *    behind `provider.ts`. See
 *    `src/test/no-direct-analytics-provider.test.ts` for the guard
 *    that keeps it that way.
 */
import {
  EVENT_PROPERTY_ALLOWLIST,
  type AnalyticsEventName,
  type AnalyticsEventProperties,
} from "./events";
import { resolveProvider, type AnalyticsProvider } from "./provider";

/**
 * Strings are capped before they reach a provider. Every legitimate
 * value in this vocabulary is a short identifier or a literal union
 * member; anything approaching this length means something
 * unintended is being passed, and truncating is safer than forwarding
 * it.
 */
const MAX_STRING_LENGTH = 120;

type SanitizedProperties = Record<string, string | number | boolean>;

/**
 * Keeps only allowlisted keys whose values are finite primitives.
 *
 * Silently dropping a bad value rather than throwing is deliberate:
 * this function runs inside product code paths, and a malformed
 * analytics property must never be able to interrupt what the reader
 * was doing. The dropped value is simply not measured.
 */
function sanitize(name: AnalyticsEventName, properties: Readonly<Record<string, unknown>>): SanitizedProperties {
  const allowed: ReadonlyArray<string> = EVENT_PROPERTY_ALLOWLIST[name];
  const sanitized: SanitizedProperties = {};

  for (const key of allowed) {
    if (!Object.prototype.hasOwnProperty.call(properties, key)) continue;
    const value = properties[key];

    if (typeof value === "string") {
      if (value.length > 0) sanitized[key] = value.slice(0, MAX_STRING_LENGTH);
      continue;
    }
    if (typeof value === "number") {
      if (Number.isFinite(value)) sanitized[key] = value;
      continue;
    }
    if (typeof value === "boolean") {
      sanitized[key] = value;
    }
    // Everything else -- objects, arrays, functions, null, undefined,
    // symbols -- is dropped without comment. There is no legitimate
    // event property of those shapes, so the only way one arrives is
    // by mistake, and forwarding it is exactly the leak this guards.
  }

  return sanitized;
}

let cachedProvider: AnalyticsProvider | null = null;

function activeProvider(): AnalyticsProvider {
  cachedProvider ??= resolveProvider();
  return cachedProvider;
}

/**
 * Records one product event. Fire-and-forget; safe to call from a
 * render path, an event handler or an effect.
 *
 * The two-argument form is typed so that the properties must match the
 * event named -- `track("world_opened", { monitor: "inflation" })` is a
 * compile error, and so is an event name that does not exist.
 */
export function track<N extends AnalyticsEventName>(name: N, properties: AnalyticsEventProperties<N>): void {
  try {
    if (!Object.prototype.hasOwnProperty.call(EVENT_PROPERTY_ALLOWLIST, name)) return;
    activeProvider().send(name, sanitize(name, properties as Readonly<Record<string, unknown>>));
  } catch {
    // Swallowed on purpose, and this is the whole point of the
    // function. A provider that throws, a blocked request, a browser
    // extension that removed the global -- none of it is the reader's
    // problem, and none of it may reach the UI. Not re-thrown, not
    // logged: a console error on every page view in a browser with an
    // ad blocker would be noise reporting a state we consider normal.
  }
}

/**
 * Test-only seam. Resets the memoized provider so a test can exercise
 * `resolveProvider` behaviour, and lets a test install a recording
 * double to assert what `track` would have sent.
 *
 * Not exported from `src/analytics/index.ts` -- application code has
 * no reason to reach it.
 */
export function __setProviderForTests(provider: AnalyticsProvider | null): void {
  cachedProvider = provider;
}
