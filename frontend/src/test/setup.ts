// Extends Vitest's `expect` with jest-dom's DOM-specific matchers
// (e.g. `toBeInTheDocument`, `toHaveAttribute`) for every test file --
// loaded once via vite.config.ts's `test.setupFiles`.
import "@testing-library/jest-dom/vitest";

// React Testing Library's automatic post-test cleanup only registers
// itself when it can find an ambient `afterEach` (Vitest/Jest globals
// mode). This project deliberately runs Vitest without `globals: true`
// (explicit imports over ambient test globals), so cleanup is
// registered explicitly here instead -- without it, each render leaks
// into the next test within a file, and queries like
// `getByRole(..., { name: ... })` start matching multiple elements.
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});
