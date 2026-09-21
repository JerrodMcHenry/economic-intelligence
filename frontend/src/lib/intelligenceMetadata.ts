/**
 * Route metadata for a permanent intelligence object (Increment #40).
 *
 * Derived entirely from structured facts through controlled templates.
 * No model, no free text, and no claim the object does not carry -- in
 * particular nothing about significance, which #39 deliberately does
 * not define.
 *
 * The description is written to make sense ALONE, in a unfurl with no
 * surrounding page, which is the only context a shared link has.
 */
import type { IntelligenceObject } from "../api/intelligence.types";
import { headline, summary, worldLabel } from "./intelligenceLanguage";
import { absoluteUrl, intelligencePath } from "./siteUrl";

export interface MetaDescriptor {
  [key: string]: string | undefined;
}

const SITE_NAME = "MacroChipz";

export function intelligenceMeta(object: IntelligenceObject | null, intelligenceId: string): MetaDescriptor[] {
  if (object === null) {
    return [
      { title: `Not found — ${SITE_NAME}` },
      { name: "description", content: "No MacroChipz intelligence exists at this address." },
      // A missing object must never be indexed as though it were one.
      { name: "robots", content: "noindex" },
    ];
  }

  const title = `${headline(object)} — ${SITE_NAME}`;
  const description = `${summary(object)} ${worldLabel(object.world)}, for ${object.effective_period}. Evidence and methodology included.`;
  const url = absoluteUrl(intelligencePath(intelligenceId));

  const tags: MetaDescriptor[] = [
    { title },
    { name: "description", content: description },
    { property: "og:title", content: title },
    { property: "og:description", content: description },
    { property: "og:type", content: "article" },
    { property: "og:site_name", content: SITE_NAME },
    { name: "twitter:card", content: "summary_large_image" },
    { name: "twitter:title", content: title },
    { name: "twitter:description", content: description },
  ];

  // Absolute URLs only where the deployment origin is actually
  // configured. A guessed canonical is worse than none.
  if (url !== null) {
    tags.push({ property: "og:url", content: url });
    tags.push({ tagName: "link", rel: "canonical", href: url });
    const image = absoluteUrl(`/og/${encodeURIComponent(intelligenceId)}.png`);
    if (image !== null) {
      tags.push({ property: "og:image", content: image });
      tags.push({ property: "og:image:alt", content: headline(object) });
      tags.push({ name: "twitter:image", content: image });
    }
  }

  return tags;
}
