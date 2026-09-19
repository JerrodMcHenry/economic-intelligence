import type { ReactNode } from "react";

/**
 * A labelled content section: an optional small uppercase label above
 * an `h2`, optional intro copy, then content. The heading is wired to
 * the `<section>` via `aria-labelledby`, so every section is a named
 * landmark region for assistive technology.
 */
export function Section({
  id,
  label,
  title,
  intro,
  children,
}: {
  id: string;
  label?: string;
  title: string;
  intro?: ReactNode;
  children: ReactNode;
}) {
  const headingId = `${id}-heading`;
  return (
    <section id={id} aria-labelledby={headingId} className="scroll-mt-24">
      {label && <p className="type-label text-fg-muted">{label}</p>}
      <h2 id={headingId} className={`type-section-heading text-fg ${label ? "mt-2" : ""}`}>
        {title}
      </h2>
      {intro && <p className="mt-2 max-w-prose text-fg-secondary">{intro}</p>}
      <div className="mt-6">{children}</div>
    </section>
  );
}
