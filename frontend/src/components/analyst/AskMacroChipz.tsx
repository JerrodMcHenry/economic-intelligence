import { useId, useState } from "react";

import { track } from "../../analytics";
import { askAnalyst } from "../../api/analyst";
import type { AnalystContextRef, AnalystContextType, AnalystExplainResponse } from "../../api/analyst.types";
import * as copy from "../../lib/analystCopy";
import { Card } from "../Card";
import { Disclosure } from "../Disclosure";

/**
 * The contextual MacroChipz Analyst surface (Increment #33).
 *
 * One compact surface per page, not a chat. There is no conversation
 * history, no thread, no memory and no persona -- a question and an
 * answer about the page the reader is already looking at.
 *
 * What this component does NOT do is the important part. It collects a
 * question, names the page's context, calls the API, and renders what
 * comes back. It never assembles evidence, never decides what is true,
 * never classifies anything, and never computes an economic value.
 * Everything it displays -- including which evidence is shown -- was
 * resolved and validated server-side. Guarded by
 * `src/test/no-analyst-derivation.test.ts`.
 *
 * `available` is passed in rather than fetched here, so a page that
 * already knows the Analyst is unconfigured renders nothing heavier
 * than a short note, and an Analyst outage can never affect the
 * canonical content around it.
 */
export function AskMacroChipz({
  contextType,
  contextRef,
  available,
  headingId,
}: {
  contextType: AnalystContextType;
  contextRef: AnalystContextRef;
  available: boolean;
  headingId: string;
}) {
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState(false);
  const [answer, setAnswer] = useState<AnalystExplainResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const inputId = useId();

  if (!available) {
    return (
      <section aria-labelledby={headingId}>
        <h2 id={headingId} className="text-sm font-medium text-fg-muted">
          {copy.HEADING}
        </h2>
        <p className="mt-2 text-sm text-fg-muted">{copy.UNAVAILABLE_COPY}</p>
      </section>
    );
  }

  async function submit(asked: string) {
    const trimmed = asked.trim();
    if (trimmed.length === 0 || pending) return;

    setPending(true);
    setFailed(false);
    setAnswer(null);
    // Increment #37: records ONLY which page context the question was
    // asked from. The question text, the answer, and the evidence are
    // never sent anywhere -- see docs/architecture/product-measurement.md
    // "Prohibited data". `trimmed` is deliberately not referenced here.
    track("analyst_asked", { context_type: contextType });
    try {
      setAnswer(await askAnalyst(contextRef, trimmed));
    } catch {
      // Every failure mode -- unavailable, timed out, malformed output
      // -- is reported the same way: one honest sentence in this panel.
      // The page's canonical content is untouched either way, and the
      // reader is never shown a status code or a provider name.
      setFailed(true);
    } finally {
      setPending(false);
    }
  }

  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId} className="text-sm font-medium text-fg-muted">
        {copy.HEADING}
      </h2>
      <p className="mt-2 max-w-2xl text-sm text-fg-secondary">{copy.introCopy(contextType)}</p>

      <Card className="mt-4">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void submit(question);
          }}
        >
          <label htmlFor={inputId} className="block text-xs font-medium uppercase tracking-wide text-fg-muted">
            {copy.INPUT_LABEL}
          </label>
          <div className="mt-2 flex flex-wrap gap-2">
            <input
              id={inputId}
              type="text"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              maxLength={500}
              autoComplete="off"
              placeholder={copy.suggestedQuestions(contextType)[0]}
              className="min-w-0 flex-1 rounded-md border border-line bg-surface px-3 py-2 text-sm text-fg placeholder:text-fg-muted"
            />
            <button
              type="submit"
              disabled={pending || question.trim().length === 0}
              className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-brand-fg hover:bg-brand-hover disabled:opacity-50"
            >
              {copy.SUBMIT_LABEL}
            </button>
          </div>
        </form>

        <div className="mt-3">
          <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">{copy.SUGGESTED_HEADING}</p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {copy.suggestedQuestions(contextType).map((suggestion) => (
              <li key={suggestion}>
                <button
                  type="button"
                  disabled={pending}
                  onClick={() => {
                    setQuestion(suggestion);
                    void submit(suggestion);
                  }}
                  className="rounded-full border border-line px-3 py-1 text-xs text-fg-secondary hover:bg-surface-subtle disabled:opacity-50"
                >
                  {suggestion}
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div aria-live="polite" className="mt-4">
          {pending && (
            <p role="status" className="text-sm text-fg-muted">
              {copy.PENDING_LABEL}
            </p>
          )}

          {failed && !pending && (
            <p role="alert" className="text-sm text-feedback-error">
              {copy.ERROR_MESSAGE}
            </p>
          )}

          {answer !== null && !pending && <AnswerPanel response={answer} />}
        </div>

        <p className="mt-4 border-t border-line-subtle pt-3 text-xs text-fg-muted">{copy.ANALYST_DISCLOSURE}</p>
      </Card>
    </section>
  );
}

/**
 * The validated answer. `evidence` contains only references the backend
 * resolved against its own context packet -- an id the model invented
 * was dropped before it ever reached this component, so nothing here
 * needs to decide whether a citation is real.
 */
function AnswerPanel({ response }: { response: AnalystExplainResponse }) {
  return (
    <div className="space-y-4 text-sm">
      <div>
        <h3 className="text-xs font-medium uppercase tracking-wide text-fg-muted">{copy.ANSWER_HEADING}</h3>
        <p className="mt-1 whitespace-pre-line text-fg">{response.answer}</p>
      </div>

      {response.evidence.length > 0 && (
        <div>
          <h3 className="text-xs font-medium uppercase tracking-wide text-fg-muted">{copy.EVIDENCE_HEADING}</h3>
          <ul className="mt-2 space-y-1.5">
            {response.evidence.map((item) => (
              <li key={item.id}>
                <span className="text-fg-secondary">{item.label}</span>
                {item.value !== null && <span className="ml-2 tabular-nums text-fg">{item.value}</span>}
                {item.detail !== null && (
                  <Disclosure summary="Details">
                    <p className="text-xs text-fg-muted">{item.detail}</p>
                  </Disclosure>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {response.limitations.length > 0 && (
        <div>
          <h3 className="text-xs font-medium uppercase tracking-wide text-fg-muted">{copy.LIMITATIONS_HEADING}</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-fg-muted">
            {response.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
