import { Route, Routes } from "react-router-dom";

import { AppShell } from "./layouts/AppShell";
import { HomePage } from "./pages/Home";
import { InflationPage } from "./pages/Inflation";
import { LaborPage } from "./pages/Labor";
import { NotFoundPage } from "./pages/NotFound";
import { OverviewPage } from "./pages/Overview";
import { RatesPage } from "./pages/Rates";
import { ReleasesPage } from "./pages/Releases";
import { ThemeProvider } from "./theme/ThemeProvider";

export function App() {
  return (
    <ThemeProvider>
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
    </ThemeProvider>
  );
}

export default App;
