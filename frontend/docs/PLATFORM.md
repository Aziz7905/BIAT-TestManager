# BIAT TestManager — Frontend Documentation

**Last updated:** 2026-04-26
**Scope:** What the frontend is right now. Single source of truth. Other frontend `.md` files (`frontend-current-state.md`, `frontend-plan.md`) are historical phase notes; read this first.

---

## 1. Frontend in one paragraph

The frontend is a Vite + React 19 + TypeScript SPA that consumes the Django REST + WebSocket backend. It implements authentication, an admin section (users / teams), a projects list, and a project workspace where the user navigates the test repository tree and works inside dedicated panels: repository (suites → cases), specifications, automation (live execution + noVNC browser streaming), and test runs. The UI is intentionally workspace-first — most real work happens inside `/projects/:id` rather than across many top-level pages.

---

## 2. Stack

- **Vite** + **React 19** + **TypeScript**
- **Tailwind CSS v4** (via `@tailwindcss/vite` — no PostCSS)
- **React Router v7** (BrowserRouter)
- **Zustand v5** (auth + execution stores)
- **Axios v1** with JWT interceptor + silent refresh
- **noVNC RFB** (direct WebSocket browser pixel streaming)
- **Plus Jakarta Sans** typeface

---

## 3. Directory layout

```
frontend/src/
├─ main.tsx                  # React entry
├─ App.tsx                   # bootstraps authStore, mounts AppRouter
├─ index.css                 # Tailwind + CSS custom-property tokens
│
├─ api/
│   ├─ client.ts             # Axios + JWT request/refresh interceptors
│   ├─ accounts/             # auth, profile, users, teams
│   ├─ projects/             # projects, project tree, members
│   ├─ specs/                # source intake, specification CRUD, indexing
│   ├─ automation/           # scripts, executions, stream tickets, checkpoints
│   ├─ runs.ts               # plans, runs, run-cases, expansion
│   ├─ specs.ts              # legacy module (kept while specs/ namespace stabilises)
│   └─ testing.ts            # legacy module (kept while api/testing/ stabilises)
│
├─ store/
│   ├─ authStore.ts          # bootstrap, hasHydrated, sessionExpired, login/logout
│   └─ executionStore.ts     # live execution snapshot + WebSocket event merge
│
├─ router/
│   ├─ AppRouter.tsx         # Routes + role-aware redirects
│   └─ ProtectedRoute.tsx    # hydration-aware guard, AdminRoute
│
├─ pages/
│   ├─ LoginPage.tsx
│   ├─ ProjectsPage.tsx
│   ├─ ProjectWorkspacePage.tsx     # tabbed workspace (Repository / Specs / Automation / Runs)
│   ├─ AutomationLivePage.tsx       # full-screen live execution (steps + noVNC)
│   ├─ DashboardPage.tsx            # reporting overview (skeleton)
│   ├─ ProfilePage.tsx
│   └─ admin/                       # UsersPage, TeamsPage
│
├─ components/
│   ├─ ui/                          # Button, Input, Modal, PageHeader, EmptyState, …
│   ├─ project/
│   │   ├─ ProjectTree.tsx          # full repository tree, lazy case loading
│   │   ├─ RepositoryDetailPane.tsx # entity-aware right panel
│   │   ├─ ProjectMembersModal.tsx
│   │   ├─ tree/                    # tree CRUD widgets
│   │   ├─ case-editor/             # structured steps, preconditions, expected result
│   │   ├─ repository/              # suite/section/scenario detail panels
│   │   ├─ specs/                   # specs intake + record review
│   │   ├─ automation/
│   │   │   ├─ ProjectAutomationWorkspace.tsx
│   │   │   ├─ NoVncViewer.tsx      # RFB direct WebSocket viewer
│   │   │   └─ …                    # script editor, execution sidebar, step timeline
│   │   └─ test-runs/
│   │       └─ ProjectTestRunsWorkspace.tsx  # plans / runs / run-cases panes
│   │
└─ types/                          # auth, accounts, testing, automation, specs
```

---

## 4. Authentication

- Token storage: `localStorage` keys `biat_access` / `biat_refresh`.
- Login → `POST /api/login/` with `{ identifier, password }` (identifier accepts email **or** username).
- Axios request interceptor adds `Authorization: Bearer <access>`.
- 401 → response interceptor calls `POST /api/refresh/` once, retries the original request. Failure clears tokens + emits `biat-auth-expired` → `/login` with `state.reason="expired"`.
- `authStore` state: `user`, `accessToken`, `isAuthenticated`, `hasHydrated`, `sessionExpired`.
- `App.tsx` calls `bootstrap()` on mount; `ProtectedRoute` and `AdminRoute` wait for hydration before deciding.

### Role-based redirects

| `organization_role` | Post-login destination |
|---|---|
| `platform_owner` | `/admin/users` |
| `org_admin` | `/admin/users` |
| `member` | `/projects` |

---

## 5. Routes

| Path | Page | Guard |
|---|---|---|
| `/login` | LoginPage | none |
| `/projects` | ProjectsPage | Protected |
| `/projects/:id` | ProjectWorkspacePage | Protected |
| `/projects/:id/automation/executions/:executionId/live` | AutomationLivePage | Protected |
| `/profile` | ProfilePage | Protected |
| `/admin/users` | admin/UsersPage | AdminRoute |
| `/admin/teams` | admin/TeamsPage | AdminRoute |

---

## 6. Project workspace (the core of the product)

`ProjectWorkspacePage` is a tabbed workspace, not a multi-page section. The same project header stays in place; tabs swap the body.

### Tabs

1. **Repository** — `ProjectTree` (suite → section → scenario → case) on the left, `RepositoryDetailPane` on the right (entity-aware: shows the right detail card for whatever the user clicked). Test cases open a structured editor with revisable design fields. Tree CRUD widgets live in `components/project/tree/`.

2. **Specifications** — source intake (file / URL), parsed source-record review queue, imported `Specification` browser, traceability links from chunks back to scenarios / cases.

3. **Automation** — `ProjectAutomationWorkspace`. Three regions:
   - Execution sidebar (list of recent executions, status badges).
   - Browser panel (`NoVncViewer` — RFB direct WebSocket to Selenium Grid node noVNC). "Start" button + "Full screen" button always visible side by side. Full screen opens `AutomationLivePage`.
   - Step timeline + result panel (live updates from the WebSocket stream).

4. **Test Runs** — `ProjectTestRunsWorkspace`. Three panes: Plans · Runs · Run Cases. Each run-case shows the pinned `test_case_revision` and a status. Currently disconnected from execution results — that integration is the next planned change (see §11).

---

## 7. Live execution streaming

Two viewing surfaces share one transport:

| Surface | Where | When used |
|---|---|---|
| Inline workspace | `ProjectAutomationWorkspace` browser panel | Default — user picks an execution from the sidebar |
| Full-screen | `AutomationLivePage` | "Full screen" button or direct link |

### How it works

1. User triggers execution → backend creates `TestExecution`, returns id.
2. Frontend calls `POST /api/test-executions/{id}/stream-ticket/` → short-lived signed ticket.
3. Frontend opens `ws/executions/{id}/?ticket=…`. `executionStore` merges the initial snapshot with subsequent events:
   - `status` — execution lifecycle (queued / running / paused / passed / failed / error / cancelled)
   - `step` — `ExecutionStep` upserts (step_index, action, status, screenshot URL, error)
   - `artifact` — new `TestArtifact` rows
   - `checkpoint` — `requested` / `resolved` / `expired` (drives the resume modal)
   - `result` — final `TestResult`
4. Browser pixel stream: `NoVncViewer` opens an RFB direct WebSocket to a backend consumer, which proxies to the Grid node's noVNC endpoint. `scaleViewport=true` fits the canvas to the panel.
5. `dispatchEvent(new Event("resize"))` is fired ~1s after RFB connect to force a rescale (rescue path for late layout).

### Checkpoints (human-in-the-loop)
When the worker emits `require_human_action`, an `ExecutionCheckpoint` event arrives → modal shows title + instructions → user clicks Resume → `POST /api/test-executions/{eid}/checkpoints/{cid}/resume/` → worker continues.

---

## 8. State

### `authStore` (Zustand)
`user`, `accessToken`, `isAuthenticated`, `hasHydrated`, `sessionExpired`, `bootstrap()`, `login()` (throws on failure — caller handles), `logout()`, `clearSession()`, `syncCurrentUserProfile()`.

### `executionStore` (Zustand)
Holds the merged live snapshot for the currently-watched execution. Reducer-style merge of incoming WS events. Components subscribe to slices (steps, status, checkpoints, artifacts) to avoid full-tree re-renders.

There is intentionally **no global app-wide store** beyond auth + execution. Repository / specs / runs data is fetched per-route via Axios and held locally — keeping the architecture honest about what is actually shared state vs. transient view data.

---

## 9. Design system

Custom Tailwind v4 tokens defined as CSS custom properties in `index.css`:

| Token | RGB | Use |
|---|---|---|
| `primary` | 37 99 235 | CTA, links (blue-600) |
| `primary-light` | 219 234 254 | subtle backgrounds |
| `surface` | 255 255 255 | cards, panels |
| `bg` | 248 250 252 | page background |
| `warm` | 234 88 12 | warnings (orange-600) |
| `text` | 15 23 42 | body |
| `muted` | 100 116 139 | secondary text |
| `border` | 226 232 240 | borders |

Font: Plus Jakarta Sans (declared in `tailwind.config.ts`, falls back to system-ui).

---

## 10. API contracts the frontend depends on

### Pagination
DRF returns `{ count, next, previous, results[] }`. The `Array.isArray(data) ? data : data.results` guard is used throughout.

### Type contract drift to watch
- `UserProfile` includes `organization_role`, `team_memberships[]`, `team` (uuid), `team_name`, `notification_provider`, `notifications_enabled`. Legacy `primary_team` / `role` fields have been removed backend-side.
- `TestCase` list responses use the **summary** serializer (no `gherkin_preview`, no `version_history`, no `latest_result_status`) to avoid N+1. Full payload only on detail.
- Run expansion is filtered to `design_status=approved` — drafts are silently excluded.
- `TestExecution.trigger_type` is the canonical source-of-launch field. There is **no** `execution_mode` field — don't introduce one.

---

## 11. What works vs what's pending

### ✅ Working
- Auth, hydration, silent refresh, role-based redirects
- Admin: users + teams CRUD with paginated lists
- Project list + create
- Project workspace shell + tab routing
- Repository tree (read + most CRUD), test case editor with structured steps
- Spec intake / record review / specification browser (functional, UX still rough)
- Automation workspace: trigger execution, live step timeline, noVNC browser stream, full-screen live page, checkpoint resume modal
- Test runs workspace: plans / runs / run-cases panels (read + manual status)

### 🟡 In progress / known issues
- noVNC canvas sizing: works for manual browser sessions, still inconsistent for script executions (sizing/scaling mismatch).
- Test Runs workspace is **not yet linked to execution results** — `TestRunCase` shows manual status only. Next change: backend exposes the linked `TestExecution`, frontend renders pass/fail + artifacts inline when present, manual dropdown stays as fallback for non-automated cases.
- Reporting page (`DashboardPage`) is a skeleton — endpoints exist (`/reporting/overview`, `/pass-rate-trend`, `/failure-hotspots`), UI not built.
- `run_kind` filter (planned vs standalone vs system_generated) — depends on backend migration; once shipped, Test Runs tab hides `system_generated` by default.

### ❌ Not started
- AI test generation UI (Phase D backend) — prompt + spec + URL composer, reviewed candidate diff view.
- LangGraph live agent UI (Phase E) — agent step authoring panel à la KaneAI.
- Self-healing reviewer queue (Phase F).

---

## 12. Build order from here

1. **noVNC sizing fix** — make script executions render at correct dimensions (parity with manual browser sessions).
2. **Test Runs ↔ Execution wiring** — surface `TestExecution` results inside `TestRunCase` rows.
3. **`run_kind` filter** — once backend ships, default Test Runs tab to `planned` + `standalone`.
4. **Reporting dashboard UI** — connect to existing reporting endpoints.
5. **Specs UX polish** — traceability-first detail panels.
6. **Phase D — Reviewed AI generation UI** — composer + diff review before commit.
7. **Phase E — Live AI agent UI** — KaneAI-style authoring + live browser; reuse the existing noVNC stack.

---

## 13. Hard rules (don't relitigate)

- Workspace-first IA. Don't add top-level pages for things that belong inside a project.
- The non-AI product must be complete before AI surfaces are added. AI features sit on top, not mixed in.
- Read-first on the right panel. Editors open as modals or dedicated routes, not as inline replacements of the read view.
- Follow backend response shapes exactly. Field renames in serializers must propagate to types in the same PR.
- One execution stream consumer per execution at a time. Don't open multiple WebSockets to the same execution.
- The noVNC RFB path is primary. The iframe fallback was removed — if RFB fails, show an error, don't silently fall back.

---

## 14. Where to look in code

| Concern | Path |
|---|---|
| Routing + guards | `router/AppRouter.tsx`, `router/ProtectedRoute.tsx` |
| Auth flow | `store/authStore.ts`, `api/client.ts`, `api/accounts/auth.ts` |
| Workspace shell | `pages/ProjectWorkspacePage.tsx` |
| Repository tree | `components/project/ProjectTree.tsx` + `tree/`, `repository/` |
| Test case editor | `components/project/case-editor/` |
| Specs UI | `components/project/specs/`, `api/specs/` |
| Automation UI | `components/project/automation/` |
| Live execution | `pages/AutomationLivePage.tsx`, `components/project/automation/NoVncViewer.tsx`, `store/executionStore.ts` |
| Test Runs UI | `components/project/test-runs/` |
| Shared UI primitives | `components/ui/` |
| Design tokens | `src/index.css`, `tailwind.config.ts` |
