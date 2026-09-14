import { Route, Routes } from "react-router-dom";

import { AppShell } from "./layouts/AppShell";
import { InflationPage } from "./pages/Inflation";
import { LaborPage } from "./pages/Labor";
import { NotFoundPage } from "./pages/NotFound";
import { OverviewPage } from "./pages/Overview";
import { ReleasesPage } from "./pages/Releases";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<OverviewPage />} />
        <Route path="inflation" element={<InflationPage />} />
        <Route path="labor" element={<LaborPage />} />
        <Route path="releases" element={<ReleasesPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export default App;
