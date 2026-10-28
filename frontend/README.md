# Frontend — End-to-End LLM Testing, Benchmarking and Regression Analysis

React 19 + Vite 8 + TypeScript single-page app. It is the primary interface for the
End-to-End LLM Testing, Benchmarking and Regression Analysis platform and talks to the
FastAPI backend over a dev proxy.

Full project documentation: [`../docs/PROJECT_DOCUMENTATION.md`](../docs/PROJECT_DOCUMENTATION.md).

## Commands

```bash
npm install
npm run dev        # dev server on :5173, proxies /api, /health, /ready to :8000
npm run build      # production build to dist/
npm run lint       # oxlint
npx tsc -b --noEmit  # type-check
```

The backend must be running for the app to show data:

```bash
uvicorn backend.main:app --reload --port 8000
```

## Backend address

The dev server proxies to `http://127.0.0.1:8000` by default. Override it with
`VITE_BACKEND_URL` in a `.env` file at the repository root.

## Structure

```text
src/
├── api.ts                    Typed API client and response models
├── App.tsx                   Shell, tab routing, 10s polling, modal state
├── index.css                 Design tokens, app shell, shared view chrome
├── main.tsx                  Entry point
└── components/
    ├── Header.tsx            Brand, backend status, tab navigation
    ├── OverviewView.tsx      Regression matrix, verdict line, run ledger
    ├── BenchmarkStudioView.tsx  Dataset + provider + model run launcher
    ├── DatasetExplorerView.tsx  Paginated case browser with filters
    ├── RegressionMatrixView.tsx Two-run statistical comparison
    ├── ModelStudioView.tsx   Custom OpenAI-compatible endpoint registry
    └── RunDetailModal.tsx    Per-case inspection dialog
```

## Design system

One rule governs the palette: **rose (`#f43f5e`) means regression, and nothing else.**
Every other status is neutral grey and distinguished by its label rather than its colour.

- Type: IBM Plex Sans (UI) and IBM Plex Mono (identifiers, metrics)
- Surfaces: flat and opaque — no glassmorphism, no gradient washes
- Radii: 4 / 6 / 8 / 10 px. Shadows: none
- Motion: one orchestrated moment only; `prefers-reduced-motion` is respected
- Focus: a global `:focus-visible` outline on every interactive element

Tokens live in the `:root` block of `src/index.css`. Change them there rather than
hardcoding values in components.

## Responsive behaviour

The layout is fluid down to 390px. Below 768px the regression matrix scrolls
horizontally inside its own container with the model column pinned, and ledger rows
collapse to two lines instead of stacking into cards.
