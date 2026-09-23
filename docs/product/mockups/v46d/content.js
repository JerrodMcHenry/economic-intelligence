/**
 * THE VERIFIED CONTENT, SHARED BY ALL THREE DIRECTIONS (#46D phase 1).
 *
 * Every sentence below is copied from something already reviewed and
 * committed:
 *
 *   - `frontend/src/explainers/registry.ts`        (#44)
 *   - `frontend/src/components/story/RateAuthorityQuiz.tsx`   (#46C)
 *   - `frontend/src/components/story/InfluenceExplorer.tsx`   (#46C)
 *   - the three sources verified in #45 and cited in #46C §D.4
 *
 * It lives in ONE file on purpose. A visual comparison is only fair if
 * the three directions are saying exactly the same thing, and the
 * fastest way to cheat at a design review is to give the direction you
 * like the better copy. Nothing here may be edited to flatter a layout:
 * if a direction cannot carry this text, that is a finding about the
 * direction.
 *
 * NO NEW ECONOMIC CLAIM APPEARS IN THIS FILE. In particular, nothing
 * quantifies a relationship between a Fed decision and a mortgage rate
 * — no direction, no magnitude, no timescale.
 */
window.STORY = {
  question: "Wait, the Fed doesn't set mortgage rates?",
  shortTitle: "The Fed and mortgage rates",

  misconception:
    "The common belief is that the Fed sets mortgage rates outright, so a Fed cut should mean a cheaper mortgage that week. It often does not work that way.",

  answer:
    "No. The Federal Reserve sets a short-term rate that banks charge each other overnight. Your mortgage rate is set by lenders in a market, and it is a different number reached a different way.",

  whatItIs:
    "The Federal Reserve's policy decision targets the federal funds rate — an overnight rate between banks. A 30-year mortgage is a loan lasting decades, priced by lenders competing in a market. The two are related, but one does not dial the other.",

  whatThisMeansForYou:
    "A Fed announcement does not translate directly into the rate you are quoted, and mortgage rates sometimes move before a Fed meeting or against it afterwards. Comparing lenders matters, because two lenders pricing the same conditions can still quote you different rates.",

  // ---- the quiz (verbatim from RateAuthorityQuiz.tsx) ----------------
  quizPrompt: "The Fed sets exactly one of these. Which?",
  quizHint: "Pick the one you think it is — then find out.",
  options: [
    {
      id: "mortgage",
      label: "Your 30-year mortgage rate",
      authority: "Your lender",
      reveal:
        "Lenders set this, competing with each other. This is the number the whole misconception is about — and two lenders can quote you different rates on the same day.",
      isFed: false,
    },
    {
      id: "fed-funds",
      label: "The federal funds rate",
      authority: "The Federal Reserve",
      reveal:
        "This is the one. The Fed's committee sets a target range for it — the rate banks charge each other for lending overnight. You never pay it, and you will probably never see it quoted anywhere.",
      isFed: true,
    },
    {
      id: "treasury",
      label: "The 10-year Treasury yield",
      authority: "Investors, in a market",
      reveal:
        "Investors set this by buying and selling government debt. The Fed's decisions shape what investors expect, but the Fed does not choose the number.",
      isFed: false,
    },
    {
      id: "savings",
      label: "The rate your bank pays on savings",
      authority: "Your bank",
      reveal:
        "Your bank chooses this. It moves with conditions the Fed influences, but no one at the Fed decides what your account earns.",
      isFed: false,
    },
  ],
  verdictRight:
    "Right — and notice what that means: the one rate the Fed sets is the one you never pay.",
  verdictWrong:
    "Most people pick that one. The Fed sets the federal funds rate — an overnight rate between banks, which you never pay.",

  // ---- the influences (verbatim from InfluenceExplorer.tsx) ----------
  influenceHeading: "Four things, not one chain",
  influences: [
    {
      id: "fed",
      label: "Fed policy",
      short: "Fed policy",
      detail: "Sets a short-term rate between banks, and shapes what investors expect next.",
    },
    {
      id: "treasury",
      label: "Long-term Treasury yields",
      short: "Treasury yields",
      detail: "What it costs the U.S. government to borrow for years at a time.",
    },
    {
      id: "mbs",
      label: "The market for bundled mortgages",
      short: "Bundled mortgages",
      detail: "Investors buy pools of home loans, and what they will pay feeds back into pricing.",
    },
    {
      id: "lender",
      label: "Lender costs and risks",
      short: "Lender costs",
      detail: "Credit conditions, the chance a loan is repaid early, and what each lender needs to earn.",
    },
  ],
  convergenceLabel: "The rate a lender quotes you",
  convergenceDetail:
    "All of the above, plus competition between lenders — which is why two lenders can quote different rates on the same day.",
  influenceCaveat:
    "These interact rather than forming a single chain, and their relative importance changes over time. This shows what feeds in, not a formula.",

  // ---- the conclusion ------------------------------------------------
  // Not a new claim: it is the quiz's own correct-answer reveal,
  // compressed to the sentence it was already making.
  conclusion: "The one rate the Fed sets is the one you never pay.",
  conclusionSupport:
    "The federal funds rate is what banks charge each other overnight. Your mortgage is priced by lenders, against long-term borrowing conditions, with their own costs and risks on top.",

  // ---- verification --------------------------------------------------
  basis:
    "This describes the published role of named institutions and how markets price long-term borrowing in general. MacroChipz wrote and reviewed this explanation.",
  sources: [
    {
      org: "Fannie Mae",
      title: "What Determines the Rate on a 30-Year Mortgage?",
      note:
        "Describes the 30-year rate as benchmarked to the 10-year Treasury with two spreads layered on: a primary-secondary spread reflecting origination costs, servicing and guaranty fees and lender profit, and a secondary spread compensating investors for prepayment and credit risk.",
      caveat: null,
    },
    {
      org: "Federal Reserve Bank of New York",
      title: "Staff Report 674, Understanding Mortgage Spreads",
      note:
        "Finds that yield spreads on agency mortgage-backed securities are a key determinant of homeowners' funding costs.",
      caveat:
        "A Staff Report is research by its authors and is not a position of the Bank or the Federal Reserve System, so it corroborates rather than establishes.",
    },
    {
      org: "Consumer Financial Protection Bureau",
      title: "Mortgage price dispersion",
      note:
        "Finds mortgage price dispersion often around 50 basis points of the annual percentage rate across virtually every segment of the market, and that most recent borrowers believed they would pay the same price whichever lender they chose.",
      caveat: null,
    },
  ],
  limitations: [
    "MacroChipz does not track mortgage rates and makes no forecast about where they are going.",
    "This explains the relationship in general. It does not explain why any particular rate moved on any particular day.",
  ],

  onward: [
    { label: "See the Treasury yields MacroChipz tracks", href: "/rates", note: "MacroChipz does not track mortgage rates." },
    { label: "See how many homes are being built", href: "/housing", note: "Permits, starts and completions." },
    { label: "Why does everyone watch the 10-year Treasury?", href: "/explain/why-the-10-year-matters", note: "Why the 10-year matters" },
  ],
};
