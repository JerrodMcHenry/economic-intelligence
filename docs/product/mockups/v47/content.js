/**
 * THE LIVING ECONOMY — prototype content (#47 phase 1).
 *
 * ================================================================
 * EVERY LINE HERE IS CONSTRAINED
 * ================================================================
 *
 * `description` is verbatim from `frontend/src/worlds/registry.ts`.
 *
 * `has` and `hasNot` describe what the product actually tracks today.
 * The spec's §5 rule: **no world may advertise a capability the product
 * does not have, and every world must name at least one thing it does
 * not track.** That third field is the one that earns trust, so it is
 * not optional and it is not padding.
 *
 * `why` is a consumer consequence, kept to things the reviewed explainer
 * copy already supports. Where no explainer supports one, it says what
 * the measure is for rather than inventing a stake.
 *
 * NOTHING HERE IS A FIGURE. No value, no date, no count. The homepage
 * hero renders from this file alone, which is why it survives an API
 * outage — and why it cannot imply currency it does not have.
 */
window.HOME = {
  worlds: [
    {
      id: "INFLATION",
      label: "Inflation",
      route: "/inflation",
      description: "Whether prices across the economy are rising faster or more slowly.",
      why: "Falling inflation does not mean falling prices — it means they are rising more slowly. That one distinction changes how the news reads.",
      has: "CPI and PCE, each with a published state, a versioned methodology and its revision history.",
      hasNot: "No basket-level prices, and no forecast of where inflation goes next.",
    },
    {
      id: "JOBS",
      label: "Jobs",
      route: "/jobs",
      description: "Whether employers are adding jobs, and how many people are out of work.",
      why: "Two different surveys measure the job market in two different ways, and they can disagree in the same month.",
      has: "The household and establishment surveys, side by side, with what each one actually counts.",
      hasNot: "No wages, no industry breakdown, and no state or metro detail.",
    },
    {
      id: "RATES",
      label: "Rates",
      route: "/rates",
      description:
        "What it costs the U.S. government to borrow, and what that says about longer-term borrowing.",
      why: "The Fed does not set your mortgage rate. Lenders do, against the long-term borrowing conditions tracked here.",
      has: "Treasury yields every business day \u2014 the curve, its spreads and real yields \u2014 each with a source and an as-of date.",
      hasNot: "No mortgage rates, no corporate debt, and no forecast.",
    },
    {
      id: "HOUSING",
      label: "Housing",
      route: "/housing",
      description: "How many homes are being authorised, started and finished across the country.",
      why: "Permits, starts and completions are three different stages of the same pipeline, and they move at different times.",
      has: "Census new residential construction: permits, starts and completions, at an annual rate.",
      hasNot: "No home prices, no sales, and no affordability measure.",
    },
  ],

  /**
   * THE LEDE's four states, as the #42 policy defines them.
   *
   * The prototype ships `quiet` selected. The brief is explicit: do not
   * invent a current economic headline to make a mockup look exciting.
   * `development` is shown as a LAYOUT with its figures redacted, which
   * lets the composition be reviewed without a fabricated claim
   * standing in for a real one.
   */
  ledeStates: {
    quiet: {
      kicker: "The economy",
      heading: "No new tracked change",
      body:
        "MacroChipz has not recorded a new change in the parts of the economy it tracks. That is not a claim that the economy is quiet — only that nothing new has arrived here.",
      note: "Roughly two thirds of business days have no release. This is the normal state, not a failure.",
    },
    unknown: {
      kicker: "The economy",
      heading: "Not yet known",
      body:
        "MacroChipz has not finished checking whether anything new has arrived. This is deliberately not the quiet state — saying 'nothing happened' before asking would be a claim, not a fact.",
      note: "Shown while the request is unresolved, and if it fails.",
    },
    development: {
      kicker: "The economy",
      heading: "A tracked change, when one exists",
      body:
        "The layout an eligible development uses. Figures are redacted here because inventing one to make a prototype look busy is the exact failure this policy exists to prevent.",
      note: "Only objects the eligibility policy admits reach this slot. Coverage records and first observations never do.",
    },
  },

  /** Curated, not ranked. Matches the existing featured set. */
  discovery: [
    {
      kind: "story",
      label: "Interactive story",
      question: "Wait, the Fed doesn't set mortgage rates?",
      blurb: "Six actors, and only two of them are set by anyone. Tap through the network.",
      route: "/story/fed-and-mortgage-rates",
    },
    {
      kind: "explainer",
      label: "Explainer",
      question: "Wait, inflation falling doesn't mean prices are falling?",
      blurb: "Inflation vs prices.",
      route: "/explain/inflation-vs-prices",
    },
    {
      kind: "explainer",
      label: "Explainer",
      question: "Why does everyone watch the 10-year Treasury?",
      blurb: "Why the 10-year matters.",
      route: "/explain/why-the-10-year-matters",
    },
  ],

  trust: [
    { label: "Sources & methodology", route: "/explain", note: "How every figure is produced" },
    { label: "What changed", route: "/revisions", note: "Revisions, shown rather than overwritten" },
    { label: "Release calendar", route: "/calendar", note: "When the next data is scheduled" },
  ],

  /** Verbatim. Census's Data API terms require this to be displayed. */
  censusNotice:
    "Source data: U.S. Department of the Treasury; FRED®, Federal Reserve Bank of St. Louis; U.S. Census Bureau and U.S. Department of Housing and Urban Development. This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau.",
};
