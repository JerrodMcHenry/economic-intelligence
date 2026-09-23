/**
 * The rate network story (Increment #46E).
 *
 * ================================================================
 * WHAT THESE TESTS ARE FOR
 * ================================================================
 *
 * Three groups, in ascending order of how much they matter:
 *
 *   1. **It works.** Six nodes, every one selectable by mouse and by
 *      keyboard, the panel follows the selection, focus does not move.
 *   2. **It stays usable.** Tap targets, dimming floors, reduced motion,
 *      and the two SVG traps that made the most important edge on the
 *      page invisible twice during visual exploration.
 *   3. **It did not buy any of that with accuracy.** No quantified
 *      relationship at any selection, no forecast, no exhaustive
 *      phrasing, and the canonical explainer keeps its URL and its rank.
 *
 * Group 3 is the one that matters. A beautiful diagram that quietly
 * asserts "a Fed cut lowers your mortgage rate" would be a worse product
 * than the document it replaced, and would pass every test about nodes.
 *
 * Geometry is asserted in the BROWSER, not here: jsdom has no layout
 * engine, so `getBoundingClientRect` is all zeroes and any pixel
 * assertion would be theatre. What is assertable here is the declared
 * minimum, and that is what is checked.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRoutesStub } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { STATIC_PATHS } from "../build/prerenderPaths";
import {
  DEFAULT_SELECTED_ID,
  NETWORK_CAVEAT,
  NETWORK_EDGES,
  NETWORK_NODES,
  networkNode,
} from "../explainers/rateNetwork";
import { EXPLAINER_PATHS, explainerById } from "../explainers/registry";
import { ThemeProvider } from "../theme/ThemeProvider";
import Route, { meta } from "./story.fedMortgage";

const STORY_PATH = "/story/fed-and-mortgage-rates";
const EXPLAINER_PATH = "/explain/fed-and-mortgage-rates";
const EXPLAINER = explainerById("explain.fed-and-mortgage-rates")!;

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..");
const source = (relative: string) => readFileSync(join(SRC, relative), "utf8");

/** Source with comments stripped: a comment explaining a rule contains
 *  the words the rule forbids. */
function code(relative: string): string {
  return source(relative)
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

const STORY_FILES = [
  "routes/story.fedMortgage.tsx",
  "components/story/RateNetwork.tsx",
  "components/story/NodePanel.tsx",
  "components/story/ShareCardPreview.tsx",
];

function renderStory() {
  const Stub = createRoutesStub([{ path: STORY_PATH, Component: Route }]);
  return render(
    <ThemeProvider>
      <Stub initialEntries={[STORY_PATH]} />
    </ThemeProvider>,
  );
}

const nodeButton = (id: string) =>
  document.querySelector<HTMLButtonElement>(`button[data-node="${id}"]`)!;
const edgeGroup = (key: string) => document.querySelector<SVGGElement>(`[data-edge="${key}"]`)!;

/* ================================================================
   1. IT WORKS
   ================================================================ */

describe("the network", () => {
  it("renders one button per node, each with an accessible name", async () => {
    renderStory();
    await screen.findByRole("heading", { level: 1 });

    for (const node of NETWORK_NODES) {
      const button = nodeButton(node.id);
      expect(button, node.id).toBeInTheDocument();
      expect(button.textContent, node.id).toContain(node.chip);
    }
    expect(document.querySelectorAll("button[data-node]")).toHaveLength(6);
  });

  it("opens with a node already explained, not with an empty panel", async () => {
    renderStory();
    await screen.findByRole("heading", { level: 1 });

    const panel = screen.getByLabelText("Selected node");
    const node = networkNode(DEFAULT_SELECTED_ID);
    expect(within(panel).getByRole("heading", { level: 2 })).toHaveTextContent(node.label);
    expect(panel.textContent).toContain(node.role);
    expect(nodeButton(DEFAULT_SELECTED_ID)).toHaveAttribute("aria-pressed", "true");
  });

  it.each(NETWORK_NODES.map((n) => [n.id, n.label] as const))(
    "selecting %s explains it",
    async (id, label) => {
      const user = userEvent.setup();
      renderStory();
      await screen.findByRole("heading", { level: 1 });

      await user.click(nodeButton(id));

      const panel = screen.getByLabelText("Selected node");
      expect(within(panel).getByRole("heading", { level: 2 })).toHaveTextContent(label);
      expect(panel.textContent).toContain(networkNode(id).role);
    },
  );

  it("marks exactly one node pressed at a time", async () => {
    const user = userEvent.setup();
    renderStory();
    await screen.findByRole("heading", { level: 1 });

    await user.click(nodeButton("mbs"));
    const pressed = [...document.querySelectorAll("button[data-node]")].filter(
      (b) => b.getAttribute("aria-pressed") === "true",
    );
    expect(pressed).toHaveLength(1);
    expect(pressed[0]).toHaveAttribute("data-node", "mbs");
  });

  it("is operable from the keyboard", async () => {
    const user = userEvent.setup();
    renderStory();
    await screen.findByRole("heading", { level: 1 });

    nodeButton("treasury").focus();
    await user.keyboard("{Enter}");
    expect(nodeButton("treasury")).toHaveAttribute("aria-pressed", "true");

    nodeButton("lenders").focus();
    await user.keyboard(" ");
    expect(nodeButton("lenders")).toHaveAttribute("aria-pressed", "true");
  });

  it("leaves focus on the node, because selecting is not navigating", async () => {
    const user = userEvent.setup();
    renderStory();
    await screen.findByRole("heading", { level: 1 });

    await user.click(nodeButton("mortgage-rate"));
    expect(document.activeElement).toBe(nodeButton("mortgage-rate"));
  });

  it("announces the change politely rather than stealing focus", async () => {
    renderStory();
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getByLabelText("Selected node")).toHaveAttribute("aria-live", "polite");
  });
});

/* ================================================================
   2. DIRECT VERSUS INDIRECT, AND STAYING USABLE
   ================================================================ */

describe("direct control is distinguished from influence", () => {
  it("draws exactly two direct edges", async () => {
    renderStory();
    await screen.findByRole("heading", { level: 1 });
    expect(document.querySelectorAll('[data-kind="sets"]')).toHaveLength(2);
    expect(document.querySelectorAll('[data-kind="influences"]')).toHaveLength(4);
  });

  it("says in words whether anybody sets the selected number", async () => {
    const user = userEvent.setup();
    renderStory();
    await screen.findByRole("heading", { level: 1 });

    const panel = () => screen.getByLabelText("Selected node");
    expect(panel().textContent).toContain("Directly set");

    await user.click(nodeButton("treasury"));
    // The absence of a setter is the finding, so it is stated, not omitted.
    expect(panel().textContent).toContain("Nobody sets it");
    expect(panel().textContent).toContain("priced in a market");
  });

  it("highlights the selected node's own connections and dims the rest", async () => {
    const user = userEvent.setup();
    renderStory();
    await screen.findByRole("heading", { level: 1 });

    await user.click(nodeButton("treasury"));
    for (const edge of NETWORK_EDGES) {
      const key = `${edge.from}->${edge.to}`;
      const touches = edge.from === "treasury" || edge.to === "treasury";
      expect(edgeGroup(key).getAttribute("data-state"), key).toBe(touches ? "related" : "dim");
    }
  });

  it("dims to a floor, never to invisibility", async () => {
    const user = userEvent.setup();
    renderStory();
    await screen.findByRole("heading", { level: 1 });

    await user.click(nodeButton("mortgage-rate"));
    const dimmed = [...document.querySelectorAll('[data-state="dim"]')];
    expect(dimmed.length).toBeGreaterThan(0);
    for (const g of dimmed) {
      expect(Number(g.getAttribute("opacity"))).toBeGreaterThanOrEqual(0.3);
    }
  });

  it("does not rely on brightness alone to tell the two kinds apart", async () => {
    renderStory();
    await screen.findByRole("heading", { level: 1 });
    // An influence edge is dashed; a direct edge is solid and arrowed.
    // Both survive monochrome and forced-colours rendering.
    const influence = edgeGroup("treasury->mbs");
    expect(influence.querySelector("path[stroke-dasharray]")).toBeTruthy();
    const direct = edgeGroup("fed-policy->fed-funds");
    expect(direct.querySelector("path[stroke-dasharray]")).toBeNull();
    expect(direct.querySelectorAll("path").length).toBeGreaterThan(3);
  });

  it("keeps the legend on the page", async () => {
    renderStory();
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getByText("Sets it directly")).toBeInTheDocument();
    expect(screen.getByText("Influences it")).toBeInTheDocument();
  });
});

describe("it stays usable", () => {
  it("gives every node button a real tap target", () => {
    // jsdom has no layout, so the DECLARED minimum is what is assertable
    // here; the rendered geometry is measured in the browser. `min-h-11`
    // is 44px and, unlike an SVG hit area, cannot be shrunk by a viewBox.
    const text = code("components/story/RateNetwork.tsx");
    expect(text).toMatch(/min-h-11/);
    expect(text).toMatch(/min-w-11/);
  });

  it("uses HTML buttons for interaction, never SVG role=button", () => {
    const text = code("components/story/RateNetwork.tsx");
    expect(text).not.toMatch(/role=["']button["']/);
    expect(text).toMatch(/<button/);
  });

  it("marks the decorative SVG as hidden from assistive technology", async () => {
    renderStory();
    await screen.findByRole("heading", { level: 1 });
    const svg = document.querySelector('[data-testid="rate-network"] svg')!;
    expect(svg).toHaveAttribute("aria-hidden", "true");
  });

  it("honours reduced motion on every transition it declares", () => {
    for (const file of STORY_FILES) {
      const text = code(file);
      const classLists = [...text.matchAll(/className=(?:"([^"]*)"|\{\[([\s\S]*?)\]\.join)/g)].map(
        (m) => (m[1] ?? m[2] ?? "").replace(/\s+/g, " "),
      );
      for (const classes of classLists) {
        const animates =
          /\btransition-(?!none)\w+/.test(classes) || /\btransition\b(?!-)/.test(classes);
        if (!animates) continue;
        expect(
          classes.includes("motion-reduce:transition-none"),
          `${file}: ${classes.slice(0, 70)}`,
        ).toBe(true);
      }
    }
  });

  it("avoids the two SVG unit traps that hid the most important edge", () => {
    const text = code("components/story/RateNetwork.tsx");
    // A gradient in objectBoundingBox units does not render on a
    // zero-area box, and the Fed-to-federal-funds edge is vertical.
    expect(text).toMatch(/gradientUnits="userSpaceOnUse"/);
    // A filter region is a percentage of the same zero-width box.
    expect(text).not.toMatch(/filter=/);
  });

  it("fetches nothing and shows no figure", () => {
    for (const file of STORY_FILES) {
      expect(code(file), file).not.toMatch(/\bfetch\s*\(|useEffect|apiClient|\/api\/v1/);
    }
  });
});

/* ================================================================
   3. IT DID NOT BUY ANY OF THAT WITH ACCURACY
   ================================================================ */

describe("no new economic claim", () => {
  it("quantifies no relationship, at any selection", async () => {
    const user = userEvent.setup();
    renderStory();
    await screen.findByRole("heading", { level: 1 });

    for (const node of NETWORK_NODES) {
      await user.click(nodeButton(node.id));
      const numeric =
        (document.body.textContent ?? "").match(
          /\d+(?:\.\d+)?\s*(?:%|percent|basis points?|bps)/gi,
        ) ?? [];
      // The only permitted figure is the CFPB dispersion finding, which
      // is about lenders differing from each other — not about the Fed
      // causing anything.
      expect(numeric.every((m) => /50 basis points/i.test(m)), node.id).toBe(true);
    }
  });

  it("never says a Fed decision moves mortgage rates in a direction", async () => {
    const user = userEvent.setup();
    renderStory();
    await screen.findByRole("heading", { level: 1 });
    for (const details of [...document.querySelectorAll("details")]) details.open = true;
    await user.click(nodeButton("mortgage-rate"));

    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(
      /Fed (?:cut|hike|raise|lower)s? [^.]{0,40}mortgage rates? (?:fall|rise|drop|go)/i,
    );
    expect(text).not.toMatch(/\b(?:will|should) (?:fall|rise|drop|increase|decrease)\b/i);
  });

  it("makes no forecast", async () => {
    renderStory();
    await screen.findByRole("heading", { level: 1 });
    expect(document.body.textContent ?? "").not.toMatch(
      /(?<!no )(?<!not )\bforecasts?\b|\bwe expect\b|\bwill likely\b|\bpredicts?\b/i,
    );
  });

  it("drops the exhaustive phrasing the brief called out", async () => {
    renderStory();
    await screen.findByRole("heading", { level: 1 });
    expect(document.body.textContent ?? "").not.toMatch(/six things decide/i);
  });

  it("keeps the 'not a formula' caveat permanently on the page", async () => {
    renderStory();
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getByText(NETWORK_CAVEAT)).toBeInTheDocument();
  });

  it("does not upgrade a Staff Report into a Federal Reserve position", async () => {
    renderStory();
    await screen.findByRole("heading", { level: 1 });
    expect(document.body.textContent ?? "").toMatch(
      /Staff Report is research by its authors and is not a position of the Bank/i,
    );
  });
});

describe("verification and continuation", () => {
  it("names its three sources and its own limitations", async () => {
    renderStory();
    await screen.findByRole("heading", { level: 1 });

    const sources = screen.getByText("The sources behind this").closest("details")!;
    expect(within(sources).getByText("Fannie Mae")).toBeInTheDocument();
    expect(within(sources).getByText("Federal Reserve Bank of New York")).toBeInTheDocument();
    expect(within(sources).getByText("Consumer Financial Protection Bureau")).toBeInTheDocument();

    const limits = screen
      .getByText(`What this does not tell you (${EXPLAINER.limitations!.length})`)
      .closest("details")!;
    for (const limitation of EXPLAINER.limitations!) {
      expect(within(limits).getByText(limitation)).toBeInTheDocument();
    }
  });

  it("links onward to both worlds, the related explainers and the canonical page", async () => {
    renderStory();
    await screen.findByRole("heading", { level: 1 });
    const hrefs = [...document.querySelectorAll("a")].map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/rates");
    expect(hrefs).toContain("/housing");
    expect(hrefs).toContain(EXPLAINER_PATH);
    for (const id of EXPLAINER.related) {
      expect(hrefs).toContain(`/explain/${explainerById(id)!.slug}`);
    }
  });

  it("says plainly that MacroChipz does not track mortgage rates", async () => {
    renderStory();
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getAllByText(/MacroChipz does not track mortgage rates/).length).toBeGreaterThan(0);
  });

  it("offers the existing share affordance", async () => {
    renderStory();
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getByRole("button", { name: /share/i })).toBeInTheDocument();
  });
});

describe("the story ends on somewhere to go, not on a prototype", () => {
  it("renders no share-card preview", async () => {
    // #46F removed it. A page that ends on a preview of a feature that
    // does not exist ends on an apology.
    renderStory();
    await screen.findByRole("heading", { level: 1 });
    expect(document.querySelector("figure")).toBeNull();
    expect(screen.queryByText(/Shareable discovery/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Share card/i)).not.toBeInTheDocument();
  });

  it("makes no claim about image export or native image sharing", async () => {
    renderStory();
    await screen.findByRole("heading", { level: 1 });
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/image export|export as an image|9:16|preview state/i);
  });

  it("ends on related reading, sources and a way onward", async () => {
    renderStory();
    await screen.findByRole("heading", { level: 1 });
    const sections = [...document.querySelectorAll("section[aria-labelledby]")].map((s) =>
      s.getAttribute("aria-labelledby"),
    );
    expect(sections).toContain("how-we-know");
    expect(sections).toContain("keep-going");
    // and nothing after `keep-going` except the canonical-link line
    expect(sections[sections.length - 1]).toBe("keep-going");
  });

  it("keeps the Share button, pointing at this story's own URL", async () => {
    renderStory();
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getByRole("button", { name: /share/i })).toBeInTheDocument();
  });
});

describe("the share URL is real, never fabricated", () => {
  it("uses the page's actual origin when no deployment origin is configured", async () => {
    // The suite pins VITE_SITE_URL empty. The old fallback was the bare
    // path, which copies "/story/..." into a clipboard and is useless
    // when pasted; the honest fallback is where the page actually is.
    const { default: Fresh } = await import("./story.fedMortgage");
    expect(Fresh).toBeTypeOf("function");
    renderStory();
    await screen.findByRole("heading", { level: 1 });
    // jsdom serves at http://localhost/, so that is the honest origin.
    expect(window.location.origin).toMatch(/^https?:\/\//);
  });

  it("uses the configured origin when there is one, and points at the STORY path", async () => {
    vi.resetModules();
    vi.stubEnv("VITE_SITE_URL", "https://macrochipz.com");
    const { absoluteUrl } = await import("../lib/siteUrl");
    expect(absoluteUrl(STORY_PATH)).toBe(`https://macrochipz.com${STORY_PATH}`);
    // ...and not the canonical explainer, which is a different page.
    expect(absoluteUrl(STORY_PATH)).not.toContain("/explain/");
  });
});

describe("the prototype stays additive and reversible", () => {
  it("does not touch the canonical explainer or its URL", () => {
    expect(EXPLAINER_PATHS).toContain(EXPLAINER_PATH);
    expect(STATIC_PATHS).toContain(EXPLAINER_PATH);
    expect(STATIC_PATHS).toContain(STORY_PATH);
  });

  it("still declares itself noindex", () => {
    expect(meta() as Array<Record<string, string>>).toContainEqual({
      name: "robots",
      content: "noindex",
    });
  });

  it("still points its canonical at the explainer, not at itself", async () => {
    vi.resetModules();
    vi.stubEnv("VITE_SITE_URL", "https://macrochipz.com");
    const { meta: fresh } = await import("./story.fedMortgage");
    const tags = fresh() as Array<Record<string, string>>;
    expect(tags).toContainEqual({
      tagName: "link",
      rel: "canonical",
      href: `https://macrochipz.com${EXPLAINER_PATH}`,
    });
    expect(tags.some((t) => t.rel === "canonical" && t.href?.includes("/story/"))).toBe(false);
  });
});

afterEach(() => {
  vi.unstubAllEnvs();
});
