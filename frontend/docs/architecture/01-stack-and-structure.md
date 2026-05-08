# 01 — Stack and Structure

**Stack details. Directory layout. File conventions.**

---

## 1. The stack in detail

### 1.1 Core
- **Vite 5** — build tool. Fast dev server, ES modules, HMR. Tailwind v4 is wired via the `@tailwindcss/vite` plugin (no PostCSS).
- **React 19** — uses the new compiler-friendly patterns. Don't use `FormEvent` — use `{ preventDefault(): void }` inline types on handlers.
- **TypeScript** — strict mode. Types reflect backend serializer shapes exactly.

### 1.2 Routing
- **React Router v7** — `BrowserRouter`. Path-based routing. No data routers (kept simple).

### 1.3 State
- **Zustand v5** — only two stores: `authStore`, `executionStore`. No global app state.

### 1.4 HTTP
- **Axios v1** — single `client.ts` instance with JWT request interceptor and silent-refresh response interceptor.

### 1.5 Streaming
- **noVNC RFB** — direct WebSocket connection to backend's noVNC consumer. The RFB library handles the VNC protocol entirely client-side.
- **Native WebSocket** — for execution event streams (status, step, artifact, checkpoint events).

### 1.6 Styling
- **Tailwind CSS v4** — declared inline in `index.css` via `@import "tailwindcss"`. Custom tokens via CSS custom properties on `:root`.
- **Plus Jakarta Sans** — typeface, declared in `tailwind.config.ts` with system-ui fallback.

### 1.7 Build output
- Static SPA — vanilla `index.html` + bundled JS/CSS. Served by any static file server. No SSR.

---

## 2. Directory layout

```
frontend/src/
├─ main.tsx                  # React 19 entry point
├─ App.tsx                   # Bootstraps authStore, mounts AppRouter
├─ index.css                 # Tailwind import + CSS custom-property tokens
│
├─ api/
│   ├─ client.ts             # Axios instance + JWT request/refresh interceptors
│   ├─ accounts/             # auth, profile, users, teams
│   ├─ projects/             # projects, project tree, members
│   ├─ specs/                # source intake, specification CRUD, indexing
│   ├─ automation/           # scripts, executions, stream tickets, checkpoints
│   ├─ runs.ts               # plans, runs, run-cases, expansion
│   ├─ ai/                   # (planned) AI generation, review queue, agent sessions
│   ├─ specs.ts              # legacy module — being subsumed by api/specs/
│   └─ testing.ts            # legacy module — being subsumed by api/testing/
│
├─ store/
│   ├─ authStore.ts          # bootstrap, hasHydrated, sessionExpired, login/logout
│   └─ executionStore.ts     # live execution snapshot + WebSocket event merge
│
├─ router/
│   ├─ AppRouter.tsx         # Routes + role-aware redirects
│   └─ ProtectedRoute.tsx    # Hydration-aware guard, AdminRoute
│
├─ pages/
│   ├─ LoginPage.tsx
│   ├─ ProjectsPage.tsx
│   ├─ ProjectWorkspacePage.tsx     # The tabbed workspace
│   ├─ AutomationLivePage.tsx       # Full-screen live execution
│   ├─ DashboardPage.tsx            # Reporting overview (skeleton)
│   ├─ ProfilePage.tsx
│   └─ admin/                       # UsersPage, TeamsPage
│
├─ components/
│   ├─ ui/                          # Button, Input, Modal, PageHeader, ...
│   ├─ layout/                      # AppLayout, TopNav
│   ├─ project/
│   │   ├─ ProjectTree.tsx          # Full repository tree, lazy case loading
│   │   ├─ RepositoryDetailPane.tsx # Entity-aware right panel
│   │   ├─ ProjectMembersModal.tsx
│   │   ├─ tree/                    # Tree CRUD widgets
│   │   ├─ case-editor/             # Structured steps, preconditions, expected result
│   │   ├─ repository/              # Suite/section/scenario detail panels
│   │   ├─ specs/                   # Specs intake + record review
│   │   ├─ automation/
│   │   │   ├─ ProjectAutomationWorkspace.tsx
│   │   │   ├─ NoVncViewer.tsx      # RFB direct WebSocket viewer
│   │   │   └─ ...                  # script editor, execution sidebar, step timeline
│   │   ├─ test-runs/
│   │   │   └─ ProjectTestRunsWorkspace.tsx
│   │   └─ ai/                      # (planned) review queue, agent launcher, RCA viewer
│
└─ types/                          # auth, accounts, testing, automation, specs, ai (planned)
```

---

## 3. File and naming conventions

### 3.1 Components
- **PascalCase filename** matching the default-exported component
- One component per file (with rare exceptions for tightly coupled subcomponents)
- Co-locate small helper functions in the same file; promote to `utils.ts` when reused
- Hooks live in the same directory as their consumers, prefixed `use`

### 3.2 API modules
- Pure functions returning typed promises
- One file per resource family (`projects.ts`, `executions.ts`)
- Re-exports through an `index.ts` (when the family has multiple files)

### 3.3 Types
- Mirror backend serializer field names **exactly**
- Use `null` for nullable fields (matches Django's `null=True`)
- Optional fields use `?:` only when truly optional (e.g., write-only fields)
- Enum values match backend `choices.py` constants

### 3.4 Styling
- Tailwind utility classes inline
- No `<style>` tags, no CSS-in-JS
- Repeated patterns extracted into reusable components, not utility class strings
- Color tokens reference CSS custom properties via Tailwind's `[var(--name)]` syntax

---

## 4. The legacy file situation

A few legacy files remain during the in-flight reorganization:
- `api/specs.ts` — being moved to `api/specs/` (resource subdirectory)
- `api/testing.ts` — being moved to `api/testing/`

When touching these, prefer the new directory structure. Don't introduce new code in the legacy files.

---

## 5. Imports and barrel files

### 5.1 Use barrel files only at the leaves
- `components/ui/index.ts` — yes (the UI primitives are stable)
- `components/project/tree/` — yes (tree CRUD widgets are a tight set)
- `pages/index.ts` — no (pages aren't bulk-imported)

### 5.2 No deep barrel imports
Don't write `import { A, B, C } from '@/components'`. The savings aren't worth the bundle-impact and the resolution complexity.

### 5.3 Path aliasing
Vite path aliases configured in `vite.config.ts`:
- `@/...` → `src/...`

Use the alias for cross-directory imports. Use relative paths for same-directory imports.

---

## 6. Build and dev commands

```bash
# Dev server with HMR
npm run dev

# Type check
npm run typecheck

# Production build
npm run build

# Preview production build locally
npm run preview
```

The dev server runs on `http://localhost:5173` by default. The backend runs on `http://localhost:8000`. CORS is configured on the backend to allow the dev origin.

---

## 7. The dependency philosophy

**Resist adding dependencies.** Each new dependency is a security surface, a bundle-size cost, and a maintenance burden. Before adding one, check:

1. Can the standard library / built-in browser API do this?
2. Can a few lines of custom code do this?
3. Is the dep actively maintained, well-typed, and small?

This is why the stack is intentionally minimal: no UI library, no state-management library beyond Zustand, no data-fetching library beyond Axios.

When AI features arrive (Phase D, Phase E), expect to add:
- A markdown renderer (for AI-generated text + RCA)
- A diff viewer (for reviewing AI-generated code candidates)
- Possibly a code editor (Monaco) — but only if the existing textarea-based editor proves insufficient

These are **future** additions justified by specific features. Don't preemptively add them.
