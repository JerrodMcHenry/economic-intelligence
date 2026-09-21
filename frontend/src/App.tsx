import { Route, Routes } from "react-router-dom";

import { AppShell } from "./layouts/AppShell";
import { HomePage } from "./pages/Home";
import { InflationPage } from "./pages/Inflation";
import { LaborPage } from "./pages/Labor";
import { NotFoundPage } from "./pages/NotFound";
import { OverviewPage } from "./pages/Overview";
import { RatesPage } from "./pages/Rates";
import { ReleasesPage } from "./pages/Releases";

/**
 * The routes that have not yet graduated into React Router framework
 * mode (Increment #40). Rendered by `routes/catchall.tsx`.
 *
 * `ThemeProvider` moved to `root.tsx` in #40 so that routes outside
 * this tree -- the permanent intelligence page is the first -- get the
 * theme too. Nothing else here changed.
 */
export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="overview" element={<OverviewPage />} />
        <Route path="inflation" element={<InflationPage />} />
        <Route path="labor" element={<LaborPage />} />
        <Route path="rates" element={<RatesPage />} />
        <Route path="releases" element={<ReleasesPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export default App;
