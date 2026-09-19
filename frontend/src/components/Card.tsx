import type { ReactNode } from "react";

/**
 * The base surface: a card is a very slightly lighter background plus a
 * hairline border (#27A §13) -- never a heavy shadow, glow, or hover
 * lift. `as` lets a card be a list item or article where the semantics
 * call for it.
 */
export function Card({
  as: Element = "div",
  className = "",
  children,
}: {
  as?: "div" | "li" | "article";
  className?: string;
  children: ReactNode;
}) {
  return <Element className={`rounded-lg border border-line bg-surface p-5 sm:p-6 ${className}`}>{children}</Element>;
}
