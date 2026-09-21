/**
 * Client entry (Increment #40). Replaces `src/main.tsx`.
 *
 * Hydrates the whole document rather than a `#root` div, because in
 * framework mode `root.tsx` owns `<html>`. `StrictMode` is preserved
 * from the previous entry point.
 */
import { StrictMode } from "react";
import { hydrateRoot } from "react-dom/client";
import { HydratedRouter } from "react-router/dom";

hydrateRoot(
  document,
  <StrictMode>
    <HydratedRouter />
  </StrictMode>,
);
