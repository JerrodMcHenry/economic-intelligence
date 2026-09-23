import { SITE_URL } from "../../lib/siteUrl";

/**
 * The 9:16 share card (Increment #46E).
 *
 * ================================================================
 * NOT RENDERED ANYWHERE (as of #46F)
 * ================================================================
 *
 * The story page used to show this under a "Shareable discovery"
 * heading. It was removed: a page that ends on a preview of a feature
 * that does not exist ends on an apology, and the useful ending is
 * related reading, sources and a way onward.
 *
 * Kept rather than deleted because the composition is the reviewed one
 * — takeaway, mark, attribution, no figure — and it is what a real
 * Open Graph image generator should render when #48 builds one
 * (Constitution §23: generated from the canonical object, never
 * hand-made). Whoever picks it up should re-read the two notes below
 * before shipping it.
 *
 * Its guards still run: the story test suite reads this file for the
 * no-fetch and reduced-motion checks, so it cannot rot quietly.
 *
 * ================================================================
 * RENDERED FROM THE REGISTRY, NEVER DRAWN BY HAND
 * ================================================================
 *
 * Constitution §23 is explicit: "Every OG image is generated from the
 * canonical object, never hand-made, so it cannot drift from what the
 * page says." This component takes its takeaway from the same constants
 * the page renders, so the card cannot say something the story does not.
 *
 * ================================================================
 * WHY THERE IS NO AS-OF DATE
 * ================================================================
 *
 * §23 also requires that a share card state its as-of date, so that a
 * card shared six months later does not imply currency. That rule exists
 * to protect FIGURES, and this card carries none — every claim on it is
 * an institutional role, which is why the card says so in place of a
 * date. A date here would imply the claim expires; it does not, and
 * pretending otherwise would be its own small dishonesty.
 *
 * If this ever carries a number, it needs the date. The rule is not
 * waived, it is inapplicable.
 *
 * ================================================================
 * THE URL IS A PREVIEW, NOT A PRODUCTION LINK
 * ================================================================
 *
 * Nothing is deployed. `VITE_SITE_URL` is unset outside a release build,
 * and the brief forbids inventing a production URL — so when there is no
 * configured origin the card says PREVIEW rather than printing a
 * plausible-looking domain that does not resolve.
 */
export function ShareCardPreview({
  takeaway,
  support,
}: {
  takeaway: string;
  support: string;
}) {
  const destination = SITE_URL === null ? null : `${SITE_URL}/explain/fed-and-mortgage-rates`;

  return (
    <figure className="m-0 sm:grid sm:grid-cols-[auto_minmax(0,1fr)] sm:items-center sm:gap-8">
      <figcaption className="type-label mb-3 text-center text-fg-muted sm:hidden">
        Share card &middot; 9:16 {destination === null && <span>&middot; preview</span>}
      </figcaption>

      {/*
        THE ASPECT RATIO IS THE EXPORT SPEC, so it is fixed at 9:16 and
        the width is what grows: 270px on a phone, 320px from `sm`. A
        preview that is not the shape of the thing it previews is not a
        preview.
      */}
      <div
        className="mx-auto flex w-[270px] flex-col rounded-2xl border-2 border-[#a2b0ff] p-5 sm:mx-0 sm:w-[320px] sm:p-6"
        style={{
          aspectRatio: "9 / 16",
          background:
            "radial-gradient(120% 52% at 84% -4%, rgba(124,96,240,.38) 0%, transparent 62%)," +
            "radial-gradient(100% 46% at 6% 86%, rgba(186,122,240,.28) 0%, transparent 66%)," +
            "linear-gradient(176deg, #0f0a1e 0%, #0b0817 50%, #07050e 100%)",
        }}
      >
        <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-[0.16em]">
          <span className="text-fg">
            Macro<span className="text-[#a2b0ff]">Chipz</span>
          </span>
          <span className="text-fg-muted">Rates</span>
        </div>

        <div className="flex flex-1 flex-col justify-center">
          {/* The claim, drawn. Two chips and one lit connection: the Fed
              reaches the rate it sets, and stops there. */}
          <svg viewBox="0 0 220 118" aria-hidden="true" className="mb-4 w-full">
            <rect x="66" y="4" width="88" height="26" rx="8" fill="#e9ebef" />
            <text
              x="110"
              y="22"
              textAnchor="middle"
              fontSize="11"
              fontWeight="700"
              fill="#0b0817"
              fontFamily="ui-sans-serif, -apple-system, system-ui, sans-serif"
            >
              FOMC
            </text>
            <path
              d="M 110 32 L 16 32 L 16 62 L 24 62"
              fill="none"
              stroke="#a2b0ff"
              strokeWidth="2.6"
              strokeLinecap="round"
            />
            <rect
              x="24"
              y="48"
              width="168"
              height="28"
              rx="9"
              fill="rgba(124,96,240,.3)"
              stroke="#a2b0ff"
              strokeWidth="1.6"
            />
            <text
              x="110"
              y="66"
              textAnchor="middle"
              fontSize="11"
              fontWeight="700"
              fill="#f4f5ff"
              fontFamily="ui-sans-serif, -apple-system, system-ui, sans-serif"
            >
              federal funds rate
            </text>
            <circle cx="16" cy="96" r="2.6" fill="#6f7488" />
            <rect
              x="32"
              y="84"
              width="160"
              height="26"
              rx="9"
              fill="none"
              stroke="#4a4761"
              strokeWidth="1.4"
              strokeDasharray="3 4"
            />
            <text
              x="114"
              y="101"
              textAnchor="middle"
              fontSize="10.5"
              fontWeight="700"
              fill="#979ca3"
              fontFamily="ui-sans-serif, -apple-system, system-ui, sans-serif"
            >
              your mortgage rate
            </text>
          </svg>

          <p className="m-0 text-[21px] font-bold leading-[1.08] tracking-tight text-fg sm:text-[25px]">
            {takeaway}
          </p>
          <p className="mt-2 text-[11.5px] leading-snug text-fg-secondary sm:mt-2.5 sm:text-[13px]">{support}</p>
        </div>

        <div className="flex items-end justify-between gap-2 border-t border-white/10 pt-3 text-[8.5px] font-bold uppercase leading-tight tracking-wider text-fg-muted">
          <span>
            Fannie Mae &middot; NY Fed &middot; CFPB
            <br />
            Institutional roles, not market data
          </span>
          <span className="shrink-0 text-right">{destination === null ? "Preview" : "macrochipz"}</span>
        </div>
      </div>

      {/*
        The panel beside the card, which is also where the honesty lives.
        Two claims are NOT made here, deliberately: that the card can be
        exported as an image, and that native sharing of that image
        works. Neither is implemented, so neither is advertised — what
        exists is a layout preview and the existing link-sharing button
        above it.
      */}
      <div className="mt-4 sm:mt-0">
        <p className="type-label hidden text-fg-muted sm:block">
          Share card &middot; 9:16 {destination === null && <span>&middot; preview</span>}
        </p>
        <p className="mt-0 max-w-prose text-center text-xs leading-relaxed text-fg-muted sm:mt-3 sm:text-left sm:text-sm">
          {destination === null
            ? "Preview state: no deployment origin is configured, so the card shows no destination rather than inventing one."
            : `Links to ${destination}`}
        </p>
        <p className="mt-2 max-w-prose text-center text-xs leading-relaxed text-fg-muted sm:text-left">
          This is a layout preview at the real 9:16 export ratio. Image export and native
          image sharing are not implemented; the Share button above copies the page link.
        </p>
      </div>
    </figure>
  );
}
