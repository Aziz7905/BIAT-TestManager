# BIAT TestManager — Frontend Documentation

**Last updated:** 2026-05-08
**Status:** Single source of truth for the frontend application

---

## What this document is

This is the **master document** for the frontend SPA. Read this first. It explains:

1. What the frontend is and what it shouldn't try to be
2. The IA (Information Architecture) — workspace-first, not page-sprawl
3. Where to find detailed documentation for each surface
4. The current state and the next steps

For the backend's perspective, see `Backend/biat_testmanager/docs/PLATFORM.md`.

---

## 1. The frontend in one paragraph

A Vite + React 19 + TypeScript SPA that consumes the Django REST + WebSocket backend. It implements authentication, an admin section (users / teams), a projects list, and a **workspace-first** project view where most of the actual work happens. Inside `/projects/:id`, the user navigates a four-tab workspace: **Repository** (test cases), **Specifications** (requirements), **Test Runs** (planning + execution), and **Automation** (live execution + AI agent sessions). The frontend is workspace-first by design — top-level pages are kept minimal and the rich functionality lives inside the project workspace.

---

## 2. The product principle that drives the IA

The platform is the bank's QA workflow. A QA team member spends **most of their time inside one project**. The IA must make that natural — not forcing them to navigate across many top-level pages.

**Workspace-first means:**
- Top-level pages: login, projects list, profile, admin
- Everything else: lives inside `/projects/:id` as tabs, panels, and modals
- Cross-project navigation: switch projects via a project picker, not a top-level "Test Cases" page

This is intentional. It maps to how the user thinks: *"I'm working on the Banking App today"* — not *"I'm using the Test Cases module across all projects."*

---

## 3. Stack

- **Vite** + **React 19** + **TypeScript**
- **Tailwind CSS v4** (via `@tailwindcss/vite` plugin — no PostCSS)
- **React Router v7** (BrowserRouter)
- **Zustand v5** (auth + execution stores only — no global app state)
- **Axios v1** with JWT interceptor + silent refresh
- **noVNC RFB** library for direct WebSocket browser pixel streaming
- **Plus Jakarta Sans** typeface

**No:**
- Redux / RTK / TanStack Query — overengineering for this scope
- Component library (MUI, Chakra) — Tailwind v4 + custom components is enough
- SSR / Next — pure SPA, JWT-authenticated, served as static assets

---

## 4. Apps and surfaces

The frontend covers four backend layers (mapped to the three-layer backend architecture):

| Frontend surface | Backend layer | What it does |
|---|---|---|
| **Auth + Profile + Admin** | Layer 1 (accounts) | Login, password change, user management, team management |
| **Projects** + **Repository tab** + **Test Runs tab** + **Specifications tab** | Layer 1 (data management) | TestRail-style: organize, plan, manage. Also: ingest results from external CI / IDE via the hybrid path. |
| **Automation tab** + **AutomationLivePage** | Layer 2 (regression + interactive execution) | Run scripts, watch executions on opt-in basis, debug failures via debug rerun |
| **AI surfaces** (Phase E + D) — planned | Layer 3 (AI agent) | KaneAI-style: generate tests, agent sessions (always-on noVNC), review queue, RCA |

---

## 5. Top-level routes

| Path | Page | Guard |
|---|---|---|
| `/login` | LoginPage | none |
| `/projects` | ProjectsPage | Protected |
| `/projects/:id` | ProjectWorkspacePage | Protected |
| `/projects/:id/automation/executions/:executionId/live` | AutomationLivePage | Protected |
| `/profile` | ProfilePage | Protected |
| `/admin/users` | UsersPage | AdminRoute |
| `/admin/teams` | TeamsPage | AdminRoute |
| (planned) `/projects/:id/ai/review-queue` | AIReviewQueuePage | Protected |

The list is intentionally short. **No "all test cases across all projects" page. No "all executions" page. No "all specs" page.** Everything is per-project.

### 5.1 Role-based redirects after login
| `organization_role` | Post-login destination |
|---|---|
| `platform_owner` | `/admin/users` |
| `org_admin` | `/admin/users` |
| `member` | `/projects` |

---

## 6. The project workspace (the heart of the product)

`ProjectWorkspacePage` is a **tabbed workspace**. The same project header stays in place; tabs swap the body.

```
┌─────────────────────────────────────────────────────────────┐
│  TopNav                                                     │
├─────────────────────────────────────────────────────────────┤
│  Project header: name, status, members, actions            │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ [Repository] [Specifications] [Test Runs] [Automation]│ │
│  └───────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                     ACTIVE TAB CONTENT                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 6.1 Repository tab
- **Left:** `ProjectTree` (suite → section → scenario → case) with lazy case loading and full CRUD
- **Right:** `RepositoryDetailPane` — entity-aware, shows the right detail card for whatever the user clicked
- **Test cases** open a structured editor modal (steps, preconditions, expected result, linked specs)
- Tree CRUD widgets in `components/project/tree/`

### 6.2 Specifications tab
- Source intake (file upload, URL, Jira link)
- Parsed source-record review queue (approve/edit/reject)
- Imported `Specification` browser
- Traceability links from chunks back to scenarios/cases

### 6.3 Test Runs tab
- Three panes: **Plans** · **Runs** · **Run Cases**
- Plans group runs into milestones / sprints
- Runs show their `run_kind` badge (planned / standalone / system_generated)
- Run Cases show pinned `test_case_revision` and current status
- Default filter: hide `system_generated` runs (they pollute the view; they're for AI agent ad-hoc executions)

### 6.4 Automation tab
- **Execution sidebar:** list of recent executions, status badges. Filtered with `exclude_user_runs=true` so only ad-hoc / interactive / diagnostic executions show — Test Runs executions stay in their own tab.
- **Browser panel:** `NoVncViewer` — RFB direct WebSocket to the noVNC consumer. Opens only when `execution.stream_enabled=True`.
- **Step timeline + result panel:** live updates from the execution stream
- "Watch this run" button — opt-in live streaming for regression / interactive runs
- "Debug Rerun" button on failed runs — creates a new `interactive`-queue execution with `stream_enabled=True`
- Full screen button → `AutomationLivePage`

### 6.5 AI tab (planned, Phase E first, then D)
- **Agent session launcher** (Step 5): prompt + spec doc + URL + optional screenshot/context → starts a LangGraph session. Always-on noVNC viewer + agent reasoning stream side by side.
- **Review queue** for AI-generated candidates (`TestCase` drafts, `AutomationScript` candidates) — promote / edit / reject before they enter the canonical repository.
- **RCA viewer** for failed runs (Step 7): renders `TestResult.ai_failure_analysis`.
- **Amendment review** during agent sessions: accept/reject scenarios discovered live by the DOMInspector.

---

## 7. Where to find the details

| Document | What it covers |
|---|---|
| [`architecture/01-stack-and-structure.md`](architecture/01-stack-and-structure.md) | Stack details, directory layout, file conventions |
| [`architecture/02-routing-and-auth.md`](architecture/02-routing-and-auth.md) | React Router setup, JWT flow, hydration, role-based redirects |
| [`architecture/03-workspace-pattern.md`](architecture/03-workspace-pattern.md) | The tabbed workspace pattern, tree + detail panel, modal vs route decisions |
| [`architecture/04-live-execution-ux.md`](architecture/04-live-execution-ux.md) | Stream policy in the UI, debug rerun, noVNC, full-screen mode, checkpoint modals |
| [`architecture/05-ai-ux.md`](architecture/05-ai-ux.md) | AI test generation UI, review queues, agent live view (Phase D + E) |
| [`architecture/06-design-system.md`](architecture/06-design-system.md) | Tailwind tokens, component conventions, typography |

Plus:

| Document | What it covers |
|---|---|
| [`roadmap.md`](roadmap.md) | The frontend build order, aligned with backend phases |

---

## 8. State management

The frontend has only **two Zustand stores**:

### 8.1 `authStore`
- `user`, `accessToken`, `isAuthenticated`, `hasHydrated`, `sessionExpired`
- `bootstrap()` — restores from localStorage
- `login()` (throws on failure — caller handles error display)
- `logout()`, `clearSession()`, `syncCurrentUserProfile()`

### 8.2 `executionStore`
- The merged live snapshot for the currently-watched execution
- Reducer-style merge of incoming WebSocket events (status, step, artifact, checkpoint, result)
- Components subscribe to slices to avoid full-tree re-renders

### 8.3 Why no global app store
Repository data, specs data, runs data — all of it is fetched per-route via Axios and held locally in component state. Nothing is "global" except auth and the one execution being watched.

This is **intentional**. A global store for repository data would create stale-data problems (which case is the "current" one? what happens when another user edits it?) and force every page to manage cache invalidation. Per-route fetching is simpler, correct, and fast enough.

---

## 9. The hard rules (don't relitigate)

1. **Workspace-first IA.** Don't add top-level pages for things that belong inside a project.
2. **The non-AI product must be complete before AI surfaces are added.** AI features sit on top — see [`05-ai-ux.md`](architecture/05-ai-ux.md).
3. **Read-first on the right panel.** Editors open as modals or dedicated routes, never as inline replacements of the read view.
4. **Follow backend response shapes exactly.** Field renames in serializers must propagate to types in the same PR.
5. **One execution stream consumer per execution at a time.** Don't open multiple WebSockets to the same execution.
6. **Live noVNC is opt-in for regression and interactive, always-on for AI agent sessions.** Default to no stream; require explicit `stream_enabled=True` (debug rerun, "Watch this run", or AI agent session).
7. **The noVNC RFB path is primary.** No iframe fallback — if RFB fails, show an error, don't silently fall back.
8. **Pre-signed URLs for artifacts.** Never proxy artifact downloads through Django.
9. **No global app state beyond auth + execution.** Page-local state for everything else.
10. **AI agent sessions have two WebSockets, not one.** `/ws/ai-sessions/{id}/browser/` for noVNC pixels, `/ws/ai-sessions/{id}/agent/` for reasoning events. Don't multiplex.

---

## 10. Where to look in code

| Concern | Path |
|---|---|
| Routing + guards | `src/router/AppRouter.tsx`, `src/router/ProtectedRoute.tsx` |
| Auth flow | `src/store/authStore.ts`, `src/api/client.ts`, `src/api/accounts/auth.ts` |
| Workspace shell | `src/pages/ProjectWorkspacePage.tsx` |
| Repository tree | `src/components/project/ProjectTree.tsx` + `tree/`, `repository/` |
| Test case editor | `src/components/project/case-editor/` |
| Specs UI | `src/components/project/specs/`, `src/api/specs/` |
| Automation UI | `src/components/project/automation/` |
| Live execution | `src/pages/AutomationLivePage.tsx`, `src/components/project/automation/NoVncViewer.tsx`, `src/store/executionStore.ts` |
| Test Runs UI | `src/components/project/test-runs/` |
| Shared UI primitives | `src/components/ui/` |
| Design tokens | `src/index.css`, `tailwind.config.ts` |
| Type definitions | `src/types/` |

---

## 11. Reading order for someone new

1. **This document** — get the big picture
2. [`architecture/01-stack-and-structure.md`](architecture/01-stack-and-structure.md) — learn the layout
3. [`architecture/02-routing-and-auth.md`](architecture/02-routing-and-auth.md) — understand how requests flow
4. [`architecture/03-workspace-pattern.md`](architecture/03-workspace-pattern.md) — internalize the workspace-first pattern
5. [`architecture/04-live-execution-ux.md`](architecture/04-live-execution-ux.md) — understand streaming and noVNC
6. [`roadmap.md`](roadmap.md) — see what's next

[`05-ai-ux.md`](architecture/05-ai-ux.md) and [`06-design-system.md`](architecture/06-design-system.md) are reference material.
