/**
 * Every route that has not yet graduated into framework mode
 * (Increment #40).
 *
 * Renders the existing `<App />` unchanged, so Home, Overview,
 * Inflation, Labor, Rates, Releases and the 404 keep their current
 * behaviour, their current tests, and their current URLs. This file is
 * the whole reason the migration is incremental rather than a rewrite.
 */
import App from "../App";

export default function CatchAll() {
  return <App />;
}
