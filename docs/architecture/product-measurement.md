# MacroChipz — Product Measurement

**Increment #37.** The authoritative description of what MacroChipz measures, why, and what it refuses to collect.

Governed by the Product Constitution §31 (Analytics / Measurement) and the implementation sequence's #37 scope. **Build with conviction; measure with humility.** Measurement exists to answer product questions after launch. It does not decide whether MacroChipz is allowed to exist, and it never gates publication of an honest finding.

---

## 1. What this is, and what it is not

**It is:** one typed event vocabulary, one `track()` function, and one provider boundary.

**It is not:** an analytics platform. There is no identity graph, no session replay, no fingerprinting, no behavioural profiling, no cohorts, no funnels, no experimentation framework, and no data warehouse. None of those is a deferred feature; they are excluded by design.

**Analytics is optional infrastructure.** MacroChipz behaves identically when analytics is disabled, blocked, unavailable, slow or misconfigured — and disabled is the default.

---

## 2. Architecture

```
component  ──>  track(name, props)  ──>  allowlist + sanitize  ──>  AnalyticsProvider.send
                (src/analytics)           (src/analytics/track)      (src/analytics/provider)
```

| File | Responsibility |
|---|---|
| `src/analytics/events.ts` | The closed event vocabulary, property types, and the runtime property allowlist |
| `src/analytics/track.ts` | The only path from an event to a provider. Filters, sanitizes, never throws |
| `src/analytics/provider.ts` | The one module that knows which service, if any, receives an event |
| `src/analytics/usePageViewed.ts` | Route-level instrumentation, including route normalization and referrer classification |
| `src/analytics/index.ts` | The public surface. `track` and `usePageViewed` only |

**Components import `src/analytics` and nothing deeper.** `src/test/no-direct-analytics-provider.test.ts` fails the build if application code imports a vendor SDK, reaches past the abstraction, or touches the test-only provider seam.

---

## 3. The event vocabulary

Ten events. Each exists because it answers a product question, and the question is recorded beside it in `events.ts`. **An event without a product question does not ship.**

| Event | Properties | Product question | Emitted today? |
|---|---|---|---|
| `page_viewed` | `route_template`, `referrer_class` | Which surfaces are used at all? | **Yes** |
| `world_opened` | `world` | Does anyone explore past the homepage, and into which world? | **Yes** |
| `evidence_expanded` | `object_type` | **Does anyone actually verify?** | **Yes** |
| `revision_opened` | `monitor` | Is the signature capability used? | **Yes** |
| `explainer_opened` | `explainer_id` | Does in-place education land, and which concepts do readers look up? | **Yes** |
| `related_followed` | `from_type`, `to_type` | Do rabbit holes work? | **Yes** |
| `analyst_asked` | `context_type` | Is the Analyst wanted where we placed it? | **Yes** |
| `share_initiated` | `object_type` | Do objects survive leaving MacroChipz? | **Active — since #40** |
| `follow_signup` | `target` | Is there a legitimate reason to return? | **Reserved — #46** |
| `empty_state_viewed` | `surface` | Does honest absence retain or repel? | **Reserved — #42** |

### 3.1 The headline metric

**`evidence_expanded` is the one that matters most.** The Product Constitution's central bet (§2, §17.4) is that *provenance*, not clarity, is MacroChipz's differentiator. If nobody opens evidence after launch, that bet is wrong — and the correct response is to revisit the product strategy, not the instrumentation.

### 3.2 Why two events are still reserved rather than emitted

*(Three, until #40 activated `share_initiated` — see §3.2.1.)*

Per the implementation sequence's rule that we do not fabricate interactions to generate events:

- **`follow_signup`** — follow/email does not exist yet (#46), and #37 was explicitly forbidden from adding it.
- **`empty_state_viewed`** — this one is a deliberate judgement rather than a missing feature. Today's empty states are *data-availability artifacts* ("no rates data yet"). The question the event exists to answer is about the **designed honest-absence state** — "nothing meaningful changed today" — which arrives with What Changed in #42. Emitting it now would measure a different thing and quietly poison the baseline.

### 3.2.1 `share_initiated` went active in #40

The first reserved event to be switched on, and it was switched on for exactly the reason §3.2 requires: **the affordance now exists.** Increment #40 shipped `ShareButton` on the permanent intelligence object page, so the question "do objects survive leaving MacroChipz?" became answerable rather than hypothetical.

What it records is deliberately thin — `object_type` and nothing else:

- **not** the URL, which would identify the specific object a reader shared;
- **not** the share text or title;
- **not** the clipboard contents;
- **not** which application the reader chose, which is attribution data the share sheet does not owe us.

Two properties are enforced by test rather than by intent (`src/components/intelligence/intelligencePage.test.tsx`): the event is emitted *before* the share attempt and `track()` never throws, so **sharing works when analytics throws and when analytics is disabled entirely**; and the emitted properties are asserted to equal `{ object_type }` exactly, with the shared origin asserted absent.

Related #40 vocabulary changes, both preserving the closed-union rule:

- `ObjectType` gained the four Structured Intelligence type names from #39.
- `RouteTemplate` gained `/intelligence/:id`, and `normalizeRoute()` collapses `/intelligence/{anything}` onto it. **The id is discarded deliberately** — reporting it would turn `page_viewed` into a reading history, which is the distinction between measuring whether objects are read and profiling who read what.

### 3.3 One acknowledged redundancy

`world_opened` overlaps `page_viewed` today, because worlds *are* routes today. It is kept as its own event for two reasons: it survives the planned `/labor` → `/jobs` rename, and it survives the 2.0 designs where a world opens without a route change. Its `world` property is self-describing; a route template requires knowing which routes are worlds.

This is the one place #37 collects slightly more than the strict minimum, and it is recorded here rather than left to be discovered.

---

## 4. Where events are emitted

Instrumentation is attached to **semantic product actions**, never to DOM coordinates or element positions, so events survive reasonable UI redesigns.

| Event | Call site | Note |
|---|---|---|
| `page_viewed`, `world_opened` | `layouts/AppShell.tsx` via `usePageViewed()` | One place. Pages remain unaware of analytics, and a future route is instrumented by existing |
| `evidence_expanded` | `components/inflation/EvidenceDisclosure.tsx`, `components/labor/EvidenceDisclosure.tsx` | Passed as `onOpen` to the shared `Disclosure` primitive |
| `explainer_opened` | `components/explanations/ExplanationTrigger.tsx` | The component has exactly one meaning at all ~16 call sites, so the event lives in it |
| `revision_opened` | `components/history/IntelligenceHistorySection.tsx` | Reuses the row's existing `onToggle` |
| `related_followed` | `components/overview/HowTheyRelate.tsx` | The only related-idea navigation that exists today |
| `analyst_asked` | `components/analyst/AskMacroChipz.tsx` | On submit, before the request |

**A note on the `Disclosure` primitive.** It gained an optional `onOpen` callback and is deliberately kept ignorant of analytics. `Disclosure` renders evidence, methodology, data-basis notes and change lists alike, so only the call site knows which product event a given instance represents. Putting the semantics at the call site is what lets one primitive serve several different events without inventing a false one.

---

## 5. Data collected

Every property is a short identifier or a member of a small literal union. **Nothing collected is free text a user produced.**

| Property | Values |
|---|---|
| `route_template` | One of the six known routes, or `unknown_route` |
| `referrer_class` | `none` \| `internal` \| `external` |
| `world` | `inflation` \| `labor` \| `rates` |
| `object_type` | `inflation_metric` \| `labor_observation` \| `monitor_state` \| `revision` \| `release` |
| `monitor` | `inflation` \| `labor` |
| `explainer_id` | A curated identifier from `src/content/explanations/`, authored by us |
| `context_type` | The Analyst page-context name |

---

## 6. Data explicitly prohibited

Not collected, and structurally prevented rather than merely avoided:

- Names, email addresses, or any personal identifier
- **Raw Analyst questions and answers** — `analyst_asked` records only the page context; the question text is never referenced at the call site
- Any economic question a user typed
- IP addresses or precise location in application-controlled properties
- Fingerprinting attributes
- Secrets, configuration values, or authentication data
- **Raw URLs or query strings.** `page_viewed` sends a normalized route *template*; an unrecognised path becomes `unknown_route`, so a pathname containing a token or an id can never be forwarded
- The referring URL. `document.referrer` is reduced to one of three classes and discarded
- Arbitrary objects from UI components

**Two layers enforce this.** The type system makes a wrong property a compile error. The runtime allowlist in `track()` drops any key not declared for that event, and any value that is not a finite string, number or boolean — so an object, an array, a function or `null` cannot pass even if a type is widened later. Strings are truncated to 120 characters.

---

## 7. Provider decision — **unresolved, and deliberately so**

**As of #37, no analytics provider has been selected. The default is the no-op, and that is the supported production state.**

This is the implementation sequence's instruction followed rather than worked around: a provider could not be responsibly chosen without a human decision, so #37 ships the abstraction and reports the decision instead of inventing one.

**What the #35 research established:**

| Option | Custom events? | Cost | Note |
|---|---|---|---|
| **Cloudflare Web Analytics** | **No — pageviews only** | Free | Free and cookieless, but cannot carry the seven custom events, so it cannot answer the headline question |
| **Plausible** | Yes | $9/mo at 10k pageviews | Cookieless, hosted, simple |
| **Umami** | Yes | Free, self-hosted | No vendor cost; adds an operational surface to run and back up |
| **Fathom** | Yes | $15/mo | Cookieless, hosted |

**The decision is a trade between a small recurring cost and a small recurring operational burden.** Both are defensible; neither is ours to pick unilaterally. Until it is made, the vocabulary is live, the call sites are wired, and nothing is sent.

**Adding a provider later is a single-file change** — implement `AnalyticsProvider` in `src/analytics/provider.ts`, add its package to `PROVIDER_SDK_PACKAGES` in the guard test, and set `VITE_ANALYTICS_PROVIDER`. No component changes.

---

## 8. Environment behaviour

| Environment | Behaviour |
|---|---|
| **Test** | **Always the no-op**, regardless of configuration. Enforced in `resolveProvider`, not left to each test's discipline — a test run cannot reach a real analytics service |
| **Development** | No-op unless `VITE_ANALYTICS_PROVIDER=debug`, which logs to the console |
| **Production** | No-op unless a provider is configured. **`debug` is refused in a production build**, so a misconfigured variable cannot ship a console logger |
| **Unrecognised value** | No-op. Analytics fails closed; misconfiguration degrades to silence rather than to an error |

Verified in the built bundle: `MODE:"production"` and `PROD:!0` are inlined, making the debug branch unreachable.

---

## 9. Failure containment

**`track()` never throws.** Every failure mode — a provider that throws, a blocked request, an ad blocker that removed a global, a malformed provider, no provider at all — ends inside its `try/catch`.

- It returns `void`, so no caller can `await` it and no navigation or render can wait on it.
- It creates no promises, so there is nothing that can reject unobserved. A provider doing network I/O owns its own asynchrony *and* its own failure.
- **It does not log on failure.** A console error on every page view in a browser with an ad blocker would be noise reporting a state we consider normal.
- A malformed property value is dropped silently rather than throwing, because `track()` runs inside product code paths and a bad analytics value must never interrupt what the reader was doing.

---

## 10. Return behaviour — what we can and cannot infer

**#36A proposed deriving a `days_since_last_visit_bucket` from the existing Since Last Visit checkpoint. #37 found that this does not work, and dropped it.**

`lib/sinceLastVisitCheckpoint.ts` stores a **server-issued `through` watermark** — a data timestamp — and its own guard test (`no-since-last-visit-derivation.test.ts`) proves the module never reads the browser's clock. Time since that watermark measures *how stale the data a reader last saw was*, **not how long ago they visited**. Reporting it as a visit interval would be exactly the fake precision the Constitution forbids.

**So return behaviour is not measured in #37.** The honest options, both deferred:

1. Rely on an analytics provider's own aggregate returning-visitor metric, once a provider exists.
2. Store a separate, analytics-owned, coarse last-seen bucket in `localStorage`.

Option 2 means new client-side storage purely for measurement, which is a decision worth making deliberately rather than by default.

**And a precision note that applies to either option:** a local checkpoint establishes behaviour *in one browser*. It does not establish a returning *person*. Any future metric must be labelled as the former.

---

## 11. Security review

Reviewed for each risk named in the #37 brief:

| Risk | Finding |
|---|---|
| Accidental sensitive-data collection | Properties are allowlisted per event and constrained to primitives. Tested with a payload containing a question and an email address; both dropped |
| Arbitrary event payloads | Impossible through the typed API; dropped by the runtime allowlist if a type is widened |
| URL / query-string leakage | Route templates only. Tested with `/leaky-path?token=sensitive` — the emitted property is `unknown_route` and the payload contains neither substring |
| Analyst prompt leakage | The question variable is not referenced at the `analyst_asked` call site. Only `context_type` is sent |
| Secret / config leakage | No property reads configuration. The only new variable is `VITE_ANALYTICS_PROVIDER`, which is a provider *name* and is documented as non-secret |
| Provider token exposure | No provider, therefore no token. A future provider's site id is client-visible by nature — normal for browser analytics, and it must never be a secret |
| XSS / injection | No analytics value is rendered into the DOM. Values flow one way, out |
| Behaviour when configuration is absent | The default and supported state: silent no-op |

**Residual risk.** A future provider's SDK executes third-party JavaScript in the reader's browser. The abstraction limits *what MacroChipz sends*; it cannot limit what a vendor's script does once loaded. Provider selection (§7) should weigh that, and a self-hosted option avoids it entirely.

---

## 12. Limitations, stated plainly

- **Behavioural proxies are not mental states.** `evidence_expanded` measures a disclosure opening. It is evidence about verification, not a measurement of "understanding", and the Constitution's WOW/UNDERSTAND stages cannot be measured directly at all.
- **Nothing is collected today**, because no provider is configured. The vocabulary is live and the call sites are wired; the numbers begin when a provider is chosen.
- **Three events are reserved** and will only produce data once #40, #42 and #46 land.
- **No return measurement** (§10).
- **No cross-device anything.** By design, permanently.
- **`world_opened` double-counts with `page_viewed`** on world routes (§3.3).
