/**
 * Foundation-level tests for the reusable explanation affordance
 * (Increment #17C). These tests exercise `ExplanationTrigger` in
 * isolation, independent of Inflation or Releases, since it's the one
 * primitive both product surfaces reuse.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Explanation } from "../../content/explanations/types";
import { ExplanationTrigger } from "./ExplanationTrigger";

const MINIMAL: Explanation = {
  id: "test.minimal",
  title: "Minimal Concept",
  definition: "A plain-English definition of the minimal concept.",
};

const FULL: Explanation = {
  id: "test.full",
  title: "Full Concept",
  definition: "A plain-English definition of the full concept.",
  whyItMatters: "Why the full concept matters to a reader.",
  sourceNote: "Methodology: test_v1.0",
};

describe("ExplanationTrigger", () => {
  it("renders a trigger that is closed by default", () => {
    render(<ExplanationTrigger explanation={MINIMAL} />);

    const trigger = screen.getByText("i").closest("details") as HTMLDetailsElement;
    expect(trigger).not.toHaveAttribute("open");
    expect(screen.queryByText(MINIMAL.definition)).not.toBeVisible();
  });

  it("has an accessible, keyboard-focusable summary control before it's opened", () => {
    render(<ExplanationTrigger explanation={MINIMAL} />);

    const summary = screen.getByText("i");
    expect(summary.closest("summary")).toHaveAttribute("aria-label", "What does Minimal Concept mean?");
  });

  it("opens on mouse click and reveals the definition", async () => {
    const user = userEvent.setup();
    render(<ExplanationTrigger explanation={MINIMAL} />);

    await user.click(screen.getByText("i"));

    const trigger = screen.getByText("i").closest("details") as HTMLDetailsElement;
    expect(trigger).toHaveAttribute("open");
    expect(screen.getByText(MINIMAL.definition)).toBeVisible();
  });

  it("is keyboard-reachable and toggled through a native <summary>, with no custom key handling that could interfere", async () => {
    // <summary>'s Enter/Space activation is native browser default-action
    // behavior (HTML Standard 4.11.1) that jsdom doesn't simulate for
    // synthetic keyboard events, so this asserts the two things that
    // together guarantee it works in a real browser: the control is
    // reachable by Tab, and it's a genuine <summary> inside a <details>
    // with no onKeyDown/onKeyPress prop overriding or blocking that
    // native behavior (confirmed by inspecting ExplanationTrigger's
    // source, not re-asserted per-test here).
    const user = userEvent.setup();
    render(<ExplanationTrigger explanation={MINIMAL} />);

    await user.tab();
    const summary = screen.getByText("i").closest("summary");
    expect(summary).toHaveFocus();
    expect(summary?.tagName).toBe("SUMMARY");
    expect(summary?.closest("details")?.tagName).toBe("DETAILS");
    expect(summary?.onkeydown).toBeNull();
  });

  it("closes again on a second activation", async () => {
    const user = userEvent.setup();
    render(<ExplanationTrigger explanation={MINIMAL} />);

    const summary = screen.getByText("i");
    await user.click(summary);
    expect(screen.getByText(MINIMAL.definition)).toBeVisible();

    await user.click(summary);
    expect(screen.queryByText(MINIMAL.definition)).not.toBeVisible();
  });

  it("renders the title and definition once opened", async () => {
    const user = userEvent.setup();
    render(<ExplanationTrigger explanation={MINIMAL} />);

    await user.click(screen.getByText("i"));

    expect(screen.getByText("Minimal Concept")).toBeInTheDocument();
    expect(screen.getByText(MINIMAL.definition)).toBeInTheDocument();
  });

  it("renders whyItMatters when present", async () => {
    const user = userEvent.setup();
    render(<ExplanationTrigger explanation={FULL} />);

    await user.click(screen.getByText("i"));

    expect(screen.getByText(FULL.whyItMatters!)).toBeInTheDocument();
  });

  it("does not render a 'why it matters' label at all when the field is absent", async () => {
    const user = userEvent.setup();
    render(<ExplanationTrigger explanation={MINIMAL} />);

    await user.click(screen.getByText("i"));

    expect(screen.queryByText(/why it matters/i)).not.toBeInTheDocument();
  });

  it("renders sourceNote when present, and omits it when absent", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<ExplanationTrigger explanation={FULL} />);
    await user.click(screen.getByText("i"));
    expect(screen.getByText(FULL.sourceNote!)).toBeInTheDocument();

    rerender(<ExplanationTrigger explanation={MINIMAL} />);
    expect(screen.queryByText(/methodology:/i)).not.toBeInTheDocument();
  });

  it("supports multiple independent triggers on the same page without collision", async () => {
    const user = userEvent.setup();
    const SECOND: Explanation = { id: "test.second", title: "Second Concept", definition: "A second, unrelated definition." };
    render(
      <div>
        <ExplanationTrigger explanation={MINIMAL} />
        <ExplanationTrigger explanation={SECOND} />
      </div>,
    );

    const triggers = screen.getAllByText("i");
    expect(triggers).toHaveLength(2);

    await user.click(triggers[0]!);
    expect(screen.getByText(MINIMAL.definition)).toBeVisible();
    expect(screen.queryByText(SECOND.definition)).not.toBeVisible();

    await user.click(triggers[1]!);
    expect(screen.getByText(SECOND.definition)).toBeVisible();
    // Opening the second does not close the first -- each <details> manages its own state independently.
    expect(screen.getByText(MINIMAL.definition)).toBeVisible();
  });

  it("gives each trigger a screen-reader-accessible name naming the concept it explains", () => {
    render(<ExplanationTrigger explanation={FULL} />);
    expect(screen.getByText("i").closest("summary")).toHaveAttribute("aria-label", "What does Full Concept mean?");
  });
});

describe("the hit target (#49B)", () => {
  /*
   * #49A measured this control at 16 x 16 CSS px in nineteen places on
   * `/rates` alone -- 36% of the 44px minimum, on the affordance a
   * reader who does not know the vocabulary most needs.
   */
  it("expands to 44px with a pseudo-element, so no layout moves", () => {
    const { container } = render(<ExplanationTrigger explanation={MINIMAL} />);
    const summary = container.querySelector("summary") as HTMLElement;
    expect(summary).not.toBeNull();

    // The icon itself is unchanged: forty-one call sites sit beside
    // headings and values, and a 44px BOX would push every one of them
    // out of line. A pseudo-element occupies no space.
    expect(summary.className).toContain("h-4");
    expect(summary.className).toContain("w-4");

    // The target is the `::before`: 44px, centred on the icon.
    expect(summary.className).toContain("before:h-11");
    expect(summary.className).toContain("before:w-11");
    expect(summary.className).toContain("before:-translate-x-1/2");
    expect(summary.className).toContain("before:-translate-y-1/2");
    // Without `relative` the pseudo-element would be positioned
    // against some ancestor and land somewhere else entirely.
    expect(summary.className).toContain("relative");
  });
});
