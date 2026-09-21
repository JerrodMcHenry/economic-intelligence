import { Link } from "react-router-dom";

import { Card } from "../components/Card";
import { Disclosure } from "../components/Disclosure";
import { Section } from "../components/Section";
import { LATEST_REVISED_DATA } from "../content/explanations/inflation";

/**
 * The MacroChipz product introduction (Increment #27B as Home;
 * renamed in #41 when `/` became the live economic surface).
 *
 * NOT ROUTED TODAY. Kept because it is the only place that explains
 * what MacroChipz is, how a conclusion is produced and why it can be
 * trusted -- onboarding content #42 will want when it designs the real
 * homepage. Deleting it to tidy up would throw away the writing and
 * keep only the regret.
 *
 * Original notes follow.
 *
 * MacroChipz Home (Increment #27B, docs/product/product-ui-ux-v1.md
 * §5-10): the entrance to the research product, separate from Overview
 * (the intelligence workspace). Answers, in order: what MacroChipz is,
 * the three questions it is built around, how a conclusion is produced,
 * why it can be trusted, and what it currently covers.
 *
 * Deliberately static: Home fetches nothing, so it never shows a
 * loading or error state and never presents a live economic
 * conclusion of its own -- current states live on Overview and the
 * domain pages, sourced from the backend.
 *
 * Honesty constraints (#27A §9, #26E/ADR-029): no claim that the
 * product "continuously" or "automatically" monitors anything --
 * scheduled maintenance is designed but not activated in production.
 * Only implemented worlds (Inflation, Jobs) are listed as coverage.
 */

const PRIMARY_CTA_CLASSES =
  "inline-flex items-center gap-2 rounded-md bg-brand px-4 py-2.5 text-sm font-semibold text-brand-fg transition-colors hover:bg-brand-hover motion-reduce:transition-none";

const CORE_QUESTIONS: ReadonlyArray<{ question: string; answer: string; answeredBy: string }> = [
  {
    question: "What is happening?",
    answer: "Each domain is classified into a named economic state by a published, versioned methodology.",
    answeredBy: "Current state",
  },
  {
    question: "What changed?",
    answer: "Changes between periods are detected and ranked, so a shift in state stands apart from a routine data update.",
    answeredBy: "Change detection",
  },
  {
    question: "Why?",
    answer: "Every conclusion opens up to the methodology and the underlying observations that produced it.",
    answeredBy: "Evidence",
  },
];

const PIPELINE: ReadonlyArray<{ step: string; description: string }> = [
  {
    step: "Trusted economic data",
    description: "Official series from FRED, organized around the economic release calendar.",
  },
  {
    step: "Deterministic analysis",
    description: "Versioned methodologies compute momentum the same way every time.",
  },
  {
    step: "Economic state",
    description: "Results are classified into a named state such as Cooling, Stable, Heating, or Mixed.",
  },
  {
    step: "Change detection",
    description: "Period-over-period changes are identified and separated from routine updates.",
  },
  {
    step: "Evidence",
    description: "Every figure traces back to the observations and rules behind it.",
  },
];

const TRUST_PRINCIPLES: ReadonlyArray<{ title: string; body: string }> = [
  {
    title: "Sourced economic data",
    body: "Every figure traces to a named FRED series — never an estimate the product invented.",
  },
  {
    title: "Deterministic calculations",
    body: "The same inputs always produce the same outputs. No randomness and no model weights in the canonical path.",
  },
  {
    title: "Versioned methodologies",
    body: "Each result names the methodology version that produced it, so the rules behind a conclusion never change silently.",
  },
  {
    title: "Reproducible conclusions",
    body: "Re-running the analysis on the same data reproduces the same economic state.",
  },
  {
    title: "Visible supporting evidence",
    body: "Every state has a “Why?” view that goes down to the individual observations.",
  },
  {
    title: "AI is interpretive, not authoritative",
    body: "Where AI is used, it may help explain results. It is never required for, and never determines, a canonical conclusion.",
  },
];

const COVERAGE: ReadonlyArray<{ to: string; name: string; description: string; series: string }> = [
  {
    to: "/inflation",
    name: "Inflation",
    description:
      "Underlying momentum in Core PCE, cross-checked against Core CPI, with headline inflation shown against the Federal Reserve’s 2% objective.",
    series: "Core PCE · Core CPI · Headline PCE · Headline CPI",
  },
  {
    to: "/jobs",
    name: "Jobs",
    description: "Payroll employment momentum and the trend in the unemployment rate, combined into one overall Jobs state.",
    series: "Nonfarm payrolls · Unemployment rate",
  },
];

export function HomeIntroPage() {
  return (
    <div className="space-y-16 sm:space-y-20">
      {/* Hero */}
      <section aria-labelledby="home-hero-heading" className="pt-2 sm:pt-6">
        <p className="type-label text-fg-muted">
          <span className="text-brand">MacroChipz</span>
          <span aria-hidden="true" className="mx-2 text-fg-faint">
            /
          </span>
          <span>Economic Intelligence</span>
        </p>
        <h1 id="home-hero-heading" className="mt-4 max-w-4xl type-display text-fg">
          Know what changed in the economy — and prove why.
        </h1>
        <p className="mt-5 max-w-2xl text-lg leading-relaxed text-fg-secondary">
          MacroChipz turns trusted macroeconomic data into reproducible economic analysis so you can understand what changed,
          how conditions are evolving, and what evidence supports the conclusion.
        </p>
        <div className="mt-8">
          <Link to="/" className={PRIMARY_CTA_CLASSES}>
            See the economy right now
            <span aria-hidden="true">→</span>
          </Link>
        </div>
      </section>

      {/* The three questions */}
      <Section id="questions" label="Built around three questions" title="What is happening, what changed, and why">
        <ol className="grid gap-4 md:grid-cols-3">
          {CORE_QUESTIONS.map((item, index) => (
            <Card as="li" key={item.question}>
              <p className="type-label text-fg-muted">
                <span className="type-numeric">{String(index + 1).padStart(2, "0")}</span>
                <span aria-hidden="true" className="mx-1.5 text-fg-faint">
                  ·
                </span>
                {item.answeredBy}
              </p>
              <h3 className="mt-3 text-xl font-semibold tracking-tight text-fg">{item.question}</h3>
              <p className="mt-2 text-fg-secondary">{item.answer}</p>
            </Card>
          ))}
        </ol>
      </Section>

      {/* How it works */}
      <Section
        id="how-it-works"
        label="How it works"
        title="From source data to a conclusion you can check"
        intro="Conclusions come from explicit, published rules applied to official data — not from a black-box model."
      >
        <ol className="grid gap-3 lg:grid-cols-5 lg:gap-0">
          {PIPELINE.map((item, index) => (
            <li key={item.step} className="relative flex gap-4 lg:flex-col lg:gap-0 lg:pr-6">
              <div className="flex flex-col items-center lg:flex-row">
                <span className="flex h-8 w-8 flex-none items-center justify-center rounded-full border border-line-strong bg-surface text-sm font-semibold text-fg type-numeric">
                  {index + 1}
                </span>
                {index < PIPELINE.length - 1 && (
                  <span aria-hidden="true" className="mt-1 w-px flex-1 bg-line-strong lg:mt-0 lg:ml-2 lg:h-px lg:w-auto" />
                )}
              </div>
              <div className="pb-4 lg:mt-4 lg:pb-0">
                <h3 className="type-card-heading text-fg">{item.step}</h3>
                <p className="mt-1 text-sm leading-relaxed text-fg-secondary">{item.description}</p>
              </div>
            </li>
          ))}
        </ol>
      </Section>

      {/* Trust model */}
      <Section
        id="trust"
        label="Trust model"
        title="Facts are sourced. Calculations are deterministic. AI is interpretive."
        intro="No probabilistic component is required for the correctness, reproducibility, or availability of any economic conclusion MacroChipz presents."
      >
        <ul className="grid gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
          {TRUST_PRINCIPLES.map((principle) => (
            <li key={principle.title} className="bg-surface p-5 sm:p-6">
              <h3 className="type-card-heading text-fg">{principle.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-fg-secondary">{principle.body}</p>
            </li>
          ))}
        </ul>
        <div className="mt-4 max-w-prose">
          <Disclosure summary={LATEST_REVISED_DATA.title}>
            <div className="space-y-2 text-sm leading-relaxed text-fg-muted">
              <p>{LATEST_REVISED_DATA.definition}</p>
              <p>{LATEST_REVISED_DATA.whyItMatters}</p>
            </div>
          </Disclosure>
        </div>
      </Section>

      {/* Current coverage */}
      <Section
        id="coverage"
        label="Current coverage"
        title="Two economic domains, analyzed in depth"
        intro="MacroChipz currently covers inflation and the labor market. Each domain has its own methodology, current state, change history, and evidence."
      >
        <ul className="grid gap-4 md:grid-cols-2">
          {COVERAGE.map((domain) => (
            <Card as="li" key={domain.to} className="flex flex-col">
              <h3 className="text-xl font-semibold tracking-tight text-fg">{domain.name}</h3>
              <p className="mt-2 flex-1 text-fg-secondary">{domain.description}</p>
              <p className="mt-4 type-meta text-fg-muted">{domain.series}</p>
              <Link
                to={domain.to}
                className="mt-4 inline-flex items-center gap-1 self-start text-sm font-semibold text-brand hover:text-brand-hover"
              >
                Open {domain.name}
                <span aria-hidden="true">→</span>
              </Link>
            </Card>
          ))}
        </ul>
      </Section>

      {/* Where next */}
      <section
        aria-labelledby="home-next-heading"
        className="flex flex-col items-start gap-4 rounded-lg border border-line bg-surface-secondary p-6 sm:flex-row sm:items-center sm:justify-between sm:p-8"
      >
        <div>
          <h2 id="home-next-heading" className="type-section-heading text-fg">
            Start with the Overview
          </h2>
          <p className="mt-1 max-w-prose text-fg-secondary">
            Current states, what changed, and upcoming releases for every covered domain, in one place.
          </p>
        </div>
        <Link to="/" className={`${PRIMARY_CTA_CLASSES} flex-none`}>
          See the economy right now
          <span aria-hidden="true">→</span>
        </Link>
      </section>
    </div>
  );
}
