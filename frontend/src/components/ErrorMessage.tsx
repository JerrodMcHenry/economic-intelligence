/**
 * Infrastructure-failure UI: shown only for a genuine `ApiError`
 * (network/HTTP failure), never for a successful response carrying a
 * canonical "unavailable" economic state -- that distinction is made by
 * the caller, not here. Never renders the underlying error's message,
 * status code, or URL; those are backend/transport details, not
 * something a reader needs or should see.
 */
export function ErrorMessage({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-lg border border-neutral-200 bg-white p-4 text-sm text-neutral-700">
      <p>{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded-md border border-neutral-300 px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50"
        >
          Retry
        </button>
      )}
    </div>
  );
}
