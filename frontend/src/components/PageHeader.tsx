import type { ReactNode } from "react";

/**
 * The one page-title pattern every route uses: an `h1` in the page-title
 * type role (optionally followed by a small inline adornment such as an
 * explanation trigger), an optional one-line description, and an
 * optional slot for page-level notes (e.g. the "Latest revised data"
 * disclosure). Carries typography and spacing only -- no width
 * constraint (the shell owns width) and no economic meaning.
 */
export function PageHeader({
  title,
  titleAdornment,
  description,
  children,
}: {
  title: string;
  titleAdornment?: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header>
      <div className="flex items-center gap-2">
        <h1 className="type-page-title text-fg">{title}</h1>
        {titleAdornment}
      </div>
      {description && <p className="mt-2 max-w-prose text-fg-secondary">{description}</p>}
      {children && <div className="mt-3">{children}</div>}
    </header>
  );
}
