# frontend/

React + TypeScript + Vite. TanStack Query for fetching and caching, Recharts for charts, React Router for routing.

## Pages

- `/`: search box with debounced queries to `/courses?query=`.
- `/course/:subject/:number`:
  - GPA and A-share history line charts.
  - Next-term prediction cards with the error band.
  - Footnote on data source and limitations.

## Rules

- Generate API types from the OpenAPI schema with `openapi-typescript`. Don't hand-write response types.
- Every data view handles loading, empty and error states.
- Keep it intentionally small. No WebSockets, auth, or state-heavy UI (those belong to a later project).
- Checks: `tsc --noEmit`, ESLint, `vite build`.
