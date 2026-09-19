/**
 * A stable, non-animated placeholder block for a section still loading.
 * Deliberately shows no numbers -- a skeleton must never be mistaken for
 * a real (e.g. zero) reading. `heightClassName` lets a caller roughly
 * match the space its real content will occupy, so nothing jumps once
 * data arrives.
 */
export function LoadingSkeleton({ heightClassName = "h-24", label }: { heightClassName?: string; label: string }) {
  return (
    <div
      role="status"
      aria-label={label}
      className={`animate-pulse rounded-lg motion-reduce:animate-none border border-line bg-surface-secondary ${heightClassName}`}
    />
  );
}
