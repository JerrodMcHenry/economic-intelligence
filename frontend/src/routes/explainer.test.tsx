/**
 * The explainer page (Increment #44).
 *
 * Written for someone arriving from a 30-second video with no context:
 * the question and the answer come before anything else, the page
 * needs no live data, and nothing on it claims more than a curated
 * explanation can.
 */
import { render, screen, within } from "@testing-library/react";
import { createRoutesStub } from "react-router";
import { describe, expect, it } from "vitest";

import { EXPLAINERS, explainerBySlug } from "../explainers/registry";
import { ThemeProvider } from "../theme/ThemeProvider";
import Route, { meta } from "./explainer";

function renderAt(slug: string) {
  const Stub = createRoutesStub([{ path: "/explain/:slug", Component: Route }]);
  return render(
    <ThemeProvider>
      <Stub initialEntries={[`/explain/${slug}`]} />
    </ThemeProvider>,
  );
}

describe("the answer comes first", () => {
  it("leads with the question as the page heading", async () => {
    renderAt("fed-and-mortgage-rates");
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
      "Wait, the Fed doesn't set mortgage rates?",
    );
  });

  it("gives the one-sentence answer before any other section", async () => {
    const { container } = renderAt("fed-and-mortgage-rates");
    await screen.findByRole("heading", { level: 1 });
    const answer = screen.getByText(/The Federal Reserve sets a short-term rate/);
    const firstSection = container.querySelector("h2");
    expect(answer.compareDocumentPosition(firstSection!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("needs no MacroChipz context to make sense", async () => {
    const { container } = renderAt("fed-and-mortgage-rates");
    await screen.findByRole("heading", { level: 1 });
    // No methodology preamble ahead of the answer.
    const beforeAnswer = (container.textContent ?? "").split("The Federal Reserve sets")[0] ?? "";
    expect(beforeAnswer).not.toMatch(/methodology|deterministic|contract_version/i);
  });
});

describe("it renders without any live data", () => {
  it("fetches nothing", async () => {
    // No fetch is stubbed at all; the page must still render fully.
    renderAt("cpi-vs-pce");
    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "What it actually is" })).toBeInTheDocument();
  });

  it("renders every explainer in the registry", async () => {
    for (const explainer of EXPLAINERS) {
      const { unmount } = renderAt(explainer.slug);
      expect(await screen.findByRole("heading", { level: 1 }), explainer.slug).toHaveTextContent(explainer.question);
      unmount();
    }
  });

  it("omits optional sections cleanly rather than rendering empty ones", async () => {
    // `what-is-a-treasury-yield` has no misconception and no
    // "what this means for you".
    renderAt("what-is-a-treasury-yield");
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("heading", { name: "What people get wrong" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "What this means for you" })).not.toBeInTheDocument();
  });

  it("shows a helpful not-found for an unknown slug", async () => {
    renderAt("not-a-real-explainer");
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("No explainer here");
    expect(screen.getAllByRole("link").length).toBeGreaterThan(0);
  });
});

describe("the flagship visual", () => {
  it("shows the influences that converge on a mortgage rate", async () => {
    renderAt("fed-and-mortgage-rates");
    await screen.findByRole("heading", { level: 1 });
    const figure = screen.getByRole("figure");
    for (const influence of ["Fed policy", "Long-term Treasury yields", "Lender costs and risks"]) {
      expect(within(figure).getByText(influence), influence).toBeInTheDocument();
    }
  });

  it("is understandable as text, without colour or hover", async () => {
    renderAt("fed-and-mortgage-rates");
    await screen.findByRole("heading", { level: 1 });
    const figure = screen.getByRole("figure");
    // Every influence carries its own explanatory sentence, and the
    // arrow is decorative.
    expect(within(figure).getByText(/Sets a short-term rate between banks/)).toBeInTheDocument();
    expect(figure.innerHTML).not.toMatch(/onMouseOver|onPointer/);
    for (const token of ["text-red", "text-green", "state-", "feedback-"]) {
      expect(figure.innerHTML, token).not.toContain(token);
    }
  });

  it("does not draw a single deterministic chain", async () => {
    renderAt("fed-and-mortgage-rates");
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getByText(/interact rather than forming a single chain/)).toBeInTheDocument();
  });
});

describe("the rabbit hole", () => {
  it("offers a small, curated set of next questions", async () => {
    renderAt("fed-and-mortgage-rates");
    await screen.findByRole("heading", { level: 1 });
    const section = screen.getByRole("region", { name: "Explore next" });
    const links = within(section).getAllByRole("link");
    expect(links.length).toBeGreaterThanOrEqual(2);
    expect(links.length).toBeLessThanOrEqual(4);
  });

  it("links to real explainer routes", async () => {
    renderAt("fed-and-mortgage-rates");
    await screen.findByRole("heading", { level: 1 });
    const section = screen.getByRole("region", { name: "Explore next" });
    for (const link of within(section).getAllByRole("link")) {
      const href = link.getAttribute("href") ?? "";
      expect(href).toMatch(/^\/explain\//);
      expect(explainerBySlug(href.replace("/explain/", "")), href).toBeDefined();
    }
  });

  it("routes into the live world as well as onward explainers", async () => {
    renderAt("fed-and-mortgage-rates");
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getByRole("link", { name: /Explore Rates/ })).toHaveAttribute("href", "/rates");
  });
});

describe("metadata", () => {
  it("gives every explainer a title and description", () => {
    for (const explainer of EXPLAINERS) {
      const tags = meta({ params: { slug: explainer.slug } });
      expect(tags[0]?.title, explainer.slug).toContain(explainer.question);
      const description = tags.find((tag) => tag.name === "description");
      expect(description?.content, explainer.slug).toBe(explainer.answer);
    }
  });

  it("carries Open Graph and Twitter tags for sharing", () => {
    const tags = meta({ params: { slug: "fed-and-mortgage-rates" } });
    for (const property of ["og:title", "og:description", "og:type", "og:site_name"]) {
      expect(tags.some((tag) => tag.property === property), property).toBe(true);
    }
    expect(tags.some((tag) => tag.name === "twitter:card")).toBe(true);
  });

  it("asks not to be indexed for an unknown slug", () => {
    const tags = meta({ params: { slug: "nope" } });
    expect(tags).toContainEqual({ name: "robots", content: "noindex" });
  });

  it("claims nothing sensational", () => {
    for (const explainer of EXPLAINERS) {
      const text = JSON.stringify(meta({ params: { slug: explainer.slug } })).toLowerCase();
      for (const word of ["shocking", "major revision", "breaking", "crisis", "must read"]) {
        expect(text, word).not.toContain(word);
      }
    }
  });
});
