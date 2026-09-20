/**
 * Behavioural tests for the contextual Analyst surface (Increment #33).
 *
 * The API module is mocked at its boundary, so no provider is contacted
 * and every outcome -- answered, unavailable, failing, slow -- is
 * reproducible.
 *
 * What these enforce is that the surface stays honest and stays
 * optional: it renders only what the backend validated, it never claims
 * evidence of its own, and when the Analyst is not configured it
 * degrades to one sentence instead of breaking the page it sits on.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { askAnalyst } from "../../api/analyst";
import type { AnalystExplainResponse } from "../../api/analyst.types";
import { ApiError } from "../../api/errors";
import * as copy from "../../lib/analystCopy";
import { AskMacroChipz } from "./AskMacroChipz";

vi.mock("../../api/analyst", () => ({ askAnalyst: vi.fn(), getAnalystAvailability: vi.fn() }));

const mockedAsk = vi.mocked(askAnalyst);

function buildResponse(overrides: Partial<AnalystExplainResponse> = {}): AnalystExplainResponse {
  return {
    answer: "MacroChipz classifies inflation as Cooling because shorter-horizon rates sit below the 12-month rate.",
    evidence: [
      {
        id: "inflation.state.core_pce",
        kind: "STATE",
        label: "Core PCE underlying momentum state",
        value: "COOLING",
        detail: "Classified for July 2026 under inflation_v1.0",
      },
    ],
    limitations: ["Covers MacroChipz's inflation assessment only."],
    metadata: {
      context_version: "analyst_context_v1",
      prompt_version: "macrochipz_analyst_v1.1",
      model: "test-model",
      evidence_references_returned: 1,
      evidence_references_dropped: 0,
    },
    ...overrides,
  };
}

beforeEach(() => {
  mockedAsk.mockReset();
  mockedAsk.mockResolvedValue(buildResponse());
});

function renderSurface(available = true) {
  return render(
    <AskMacroChipz
      contextType="INFLATION"
      contextRef={{ type: "INFLATION" }}
      available={available}
      headingId="test-analyst-heading"
    />,
  );
}

describe("availability", () => {
  it("degrades to one sentence when the Analyst is not configured", () => {
    renderSurface(false);

    expect(screen.getByText(copy.UNAVAILABLE_COPY)).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: copy.SUBMIT_LABEL })).not.toBeInTheDocument();
  });

  it("never reveals why the Analyst is unavailable", () => {
    renderSurface(false);

    const body = document.body.textContent?.toLowerCase() ?? "";
    for (const leak of ["openai", "api key", "api_key", "environment", "not set", "configure"]) {
      expect(body).not.toContain(leak);
    }
  });

  it("makes no request when unavailable", () => {
    renderSurface(false);
    expect(mockedAsk).not.toHaveBeenCalled();
  });
});

describe("asking a question", () => {
  it("does not call the Analyst until the reader asks", () => {
    renderSurface();
    expect(mockedAsk).not.toHaveBeenCalled();
  });

  it("sends only the context reference and the question, never any state", async () => {
    renderSurface();

    await userEvent.type(screen.getByRole("textbox"), "Why is inflation cooling?");
    await userEvent.click(screen.getByRole("button", { name: copy.SUBMIT_LABEL }));

    expect(mockedAsk).toHaveBeenCalledWith({ type: "INFLATION" }, "Why is inflation cooling?");
    const contextArg = mockedAsk.mock.calls[0]?.[0];
    expect(Object.keys(contextArg ?? {})).toEqual(["type"]);
  });

  it("submits on Enter from the input", async () => {
    renderSurface();

    await userEvent.type(screen.getByRole("textbox"), "What changed?{Enter}");

    expect(mockedAsk).toHaveBeenCalledWith({ type: "INFLATION" }, "What changed?");
  });

  it("will not submit an empty or whitespace-only question", async () => {
    renderSurface();

    expect(screen.getByRole("button", { name: copy.SUBMIT_LABEL })).toBeDisabled();
    await userEvent.type(screen.getByRole("textbox"), "   ");
    expect(screen.getByRole("button", { name: copy.SUBMIT_LABEL })).toBeDisabled();
    expect(mockedAsk).not.toHaveBeenCalled();
  });

  it("shows a pending state while waiting", async () => {
    mockedAsk.mockReturnValue(new Promise(() => {}));
    renderSurface();

    await userEvent.type(screen.getByRole("textbox"), "Why?{Enter}");

    expect(screen.getByRole("status")).toHaveTextContent(copy.PENDING_LABEL);
  });
});

describe("suggested questions are deterministic UI copy", () => {
  it("renders the frozen suggestions for this context without asking the model", () => {
    renderSurface();

    for (const suggestion of copy.suggestedQuestions("INFLATION")) {
      expect(screen.getByRole("button", { name: suggestion })).toBeInTheDocument();
    }
    expect(mockedAsk).not.toHaveBeenCalled();
  });

  it("asks the suggestion verbatim when one is chosen", async () => {
    renderSurface();
    const suggestion = copy.suggestedQuestions("INFLATION")[1] as string;

    await userEvent.click(screen.getByRole("button", { name: suggestion }));

    expect(mockedAsk).toHaveBeenCalledWith({ type: "INFLATION" }, suggestion);
  });

  it("offers different suggestions per context", () => {
    expect(copy.suggestedQuestions("RATES")).not.toEqual(copy.suggestedQuestions("INFLATION"));
    expect(copy.suggestedQuestions("MONITOR_HISTORY")).not.toEqual(copy.suggestedQuestions("LABOR"));
  });
});

describe("rendering a validated answer", () => {
  it("shows the answer, its evidence and its limitations", async () => {
    renderSurface();

    await userEvent.type(screen.getByRole("textbox"), "Why?{Enter}");

    expect(await screen.findByText(/MacroChipz classifies inflation as Cooling/)).toBeInTheDocument();
    const evidenceHeading = screen.getByText(copy.EVIDENCE_HEADING);
    const evidenceBlock = evidenceHeading.parentElement as HTMLElement;
    expect(within(evidenceBlock).getByText("Core PCE underlying momentum state")).toBeInTheDocument();
    expect(screen.getByText("Covers MacroChipz's inflation assessment only.")).toBeInTheDocument();
  });

  it("renders only evidence the backend returned -- it composes none itself", async () => {
    mockedAsk.mockResolvedValue(buildResponse({ evidence: [] }));
    renderSurface();

    await userEvent.type(screen.getByRole("textbox"), "Why?{Enter}");

    await screen.findByText(/MacroChipz classifies inflation as Cooling/);
    expect(screen.queryByText(copy.EVIDENCE_HEADING)).not.toBeInTheDocument();
  });

  it("exposes evidence detail behind a keyboard-accessible disclosure", async () => {
    renderSurface();

    await userEvent.type(screen.getByRole("textbox"), "Why?{Enter}");
    await screen.findByText(copy.EVIDENCE_HEADING);

    const details = screen.getByText("Details").closest("details") as HTMLElement;
    expect(details).not.toHaveAttribute("open");
    await userEvent.click(screen.getByText("Details"));
    expect(details).toHaveAttribute("open");
    expect(screen.getByText(/Classified for July 2026 under inflation_v1.0/)).toBeInTheDocument();
  });

  it("always shows the standing disclosure about what the Analyst is", () => {
    renderSurface();
    expect(screen.getByText(copy.ANALYST_DISCLOSURE)).toBeInTheDocument();
  });

  it("replaces a previous answer rather than accumulating a transcript", async () => {
    renderSurface();

    await userEvent.type(screen.getByRole("textbox"), "First?{Enter}");
    await screen.findByText(/MacroChipz classifies inflation as Cooling/);

    mockedAsk.mockResolvedValue(buildResponse({ answer: "A completely different second answer." }));
    await userEvent.click(screen.getByRole("button", { name: copy.SUBMIT_LABEL }));

    expect(await screen.findByText("A completely different second answer.")).toBeInTheDocument();
    expect(screen.queryByText(/MacroChipz classifies inflation as Cooling/)).not.toBeInTheDocument();
  });
});

describe("failure is contained to this panel", () => {
  it("shows one honest sentence and no status code when the Analyst fails", async () => {
    mockedAsk.mockRejectedValue(new ApiError("http", "Request failed with status 503.", 503));
    renderSurface();

    await userEvent.type(screen.getByRole("textbox"), "Why?{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent(copy.ERROR_MESSAGE);
    expect(screen.queryByText(/503/)).not.toBeInTheDocument();
    expect(screen.queryByText(/openai/i)).not.toBeInTheDocument();
  });

  it("stays usable after a failure", async () => {
    mockedAsk.mockRejectedValueOnce(new ApiError("network", "Could not reach the server."));
    renderSurface();

    await userEvent.type(screen.getByRole("textbox"), "Why?{Enter}");
    await screen.findByRole("alert");

    mockedAsk.mockResolvedValue(buildResponse({ answer: "Recovered answer." }));
    await userEvent.click(screen.getByRole("button", { name: copy.SUBMIT_LABEL }));

    expect(await screen.findByText("Recovered answer.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("accessibility", () => {
  it("labels the section and associates its heading", () => {
    renderSurface();

    const heading = screen.getByRole("heading", { name: copy.HEADING });
    expect(heading).toHaveAttribute("id", "test-analyst-heading");
    expect(heading.closest("section")).toHaveAttribute("aria-labelledby", "test-analyst-heading");
  });

  it("gives the question input a real label", () => {
    renderSurface();
    expect(screen.getByLabelText(copy.INPUT_LABEL)).toBe(screen.getByRole("textbox"));
  });

  it("announces the answer region politely", async () => {
    const { container } = renderSurface();
    expect(container.querySelector("[aria-live='polite']")).not.toBeNull();
  });

  it("reaches the input, the ask button and every suggestion by keyboard", async () => {
    renderSurface();

    await userEvent.tab();
    expect(screen.getByRole("textbox")).toHaveFocus();

    // The Ask button is skipped while empty (disabled), so the next stop
    // is the first suggestion -- still fully reachable without a mouse.
    await userEvent.tab();
    expect(screen.getByRole("button", { name: copy.suggestedQuestions("INFLATION")[0] as string })).toHaveFocus();
  });
});
