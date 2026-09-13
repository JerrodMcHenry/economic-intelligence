import type { ReactNode } from "react";

/**
 * The application's one responsive content-width primitive. Every
 * page's content sits inside this rather than each page inventing its
 * own max-width/padding -- keeps the shell's horizontal rhythm
 * consistent without a larger layout-component library.
 */
export function PageContainer({ children }: { children: ReactNode }) {
  return <div className="mx-auto w-full max-w-5xl px-4 sm:px-6 lg:px-8">{children}</div>;
}
