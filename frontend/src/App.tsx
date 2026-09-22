import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./layouts/AppShell";
import { CalendarPage } from "./pages/Calendar";
import { HomePage } from "./pages/Home";
import { HousingPage } from "./pages/Housing";
import { InflationPage } from "./pages/Inflation";
import { JobsPage } from "./pages/Jobs";
import { NotFoundPage } from "./pages/NotFound";
import { RatesPage } from "./pages/Rates";
import { RevisionsPage } from "./pages/Revisions";

/**
 * The routes that have not yet graduated into React Router framework
 * mode (Increment #40). Rendered by `routes/catchall.tsx`.
 *
 * CONSUMER INFORMATION ARCHITECTURE (#41, extended in #45)
 * --------------------------------------------------------
 * Primary surfaces: Home, Inflation, Jobs, Rates, Housing, Calendar.
 * Housing is the fourth economic world and the first with no
 * methodology behind it -- see `pages/Housing.tsx`. The route
 * names are the product's names -- `/jobs`, not `/labor`; `/calendar`,
 * not `/releases` -- because a URL is the most public piece of language
 * a product has.
 *
 * `/` is the canonical home and now renders what used to live at
 * `/overview`. That page's own docstring described it as "the real `/`
 * product page"; #41 simply puts it where it always said it belonged.
 * It is NOT the #42 homepage: nothing here selects, ranks, or scores
 * intelligence, and no "most important thing today" exists.
 *
 * OLD ROUTES STILL WORK. Every previous URL redirects to its successor
 * rather than 404ing, because links that were shared before #41 are
 * not the reader's mistake. `<Navigate replace>` is a CLIENT-side
 * redirect -- see `docs/architecture/rendering-and-permanent-objects.md`
 * §19 for exactly what that does and does not give us, and what a true
 * HTTP 301 still requires at the hosting layer.
 */
export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="inflation" element={<InflationPage />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="rates" element={<RatesPage />} />
        <Route path="housing" element={<HousingPage />} />
        <Route path="calendar" element={<CalendarPage />} />

        {/* Revision Intelligence (#43) is a CROSS-WORLD capability, not
            a fourth economic world -- it is deliberately absent from
            `ECONOMIC_WORLDS` and from primary navigation, and is
            reached from the worlds where revisions actually occur. */}
        <Route path="revisions" element={<RevisionsPage />} />

        {/* Compatibility. `replace` so the old URL does not sit in the
            reader's back button, waiting to bounce them again. */}
        <Route path="overview" element={<Navigate to="/" replace />} />
        <Route path="labor" element={<Navigate to="/jobs" replace />} />
        <Route path="releases" element={<Navigate to="/calendar" replace />} />

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export default App;
