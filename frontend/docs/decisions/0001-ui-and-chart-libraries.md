# 0001: Accessible UI and chart libraries

**Status:** Accepted  
**Date:** 2026-10-05

## Decision

- Use **React Aria Components** for accessible interactive primitives. It provides
  keyboard, focus, screen-reader, and internationalization behavior without imposing
  a visual system, so Life Copilot can retain its own design language.
- Use **Recharts** for dashboard charts. It supports responsive composition and an
  accessibility layer while fitting the React component model.
- Use **Lucide React** for consistent icons, always paired with visible labels or
  accessible names.
- Use CSS modules/global design tokens for the foundation. Avoid adopting a larger
  component theme until the Phase 4 screens have been migrated and compared.
- Use **Biome** for formatting and linting. The current Next.js ESLint dependency tree
  carries an unresolved dev-only advisory; Biome is supported by Next.js and keeps the
  installed dependency audit clean.

## Consequences

Shared components must preserve semantic HTML and visible focus states. Charts must
include a text summary or table fallback and enable Recharts' accessibility layer.
The libraries are foundation dependencies, not permission to rebuild Phase 5 feature
screens before their stories begin.
