# Frontend Plan

_Source of truth: backend models + serializers. This doc is updated as each phase completes._

---

## Current status (2026-04-14)

| App | Backend | Frontend | State |
|---|---|---|---|
| Accounts | ✅ Complete | ✅ Phase 1 done, gaps noted below | Polish pass needed |
| Projects | ✅ Complete | ✅ List + workspace shell + tree | Manager create missing |
| Specifications | ✅ Complete | ❌ Not started | — |
| Testing | ✅ Complete | ✅ Tree + case detail (read-only) | CRUD missing |

---

## Global architecture notes

- Stack: Vite + React 19 + TypeScript + Tailwind v4 + React Router v7 + Zustand v5 + Axios v1
- Auth: JWT (biat_access / biat_refresh in localStorage), silent refresh on 401, pending queue pattern
- authStore has: `bootstrap()`, `hasHydrated`, `sessionExpired`, `clearSession()` — all solid
- App.tsx calls `bootstrap()` on mount, listens for `biat-auth-expired` custom event
- ProtectedRoute is hydration-aware (waits for `hasHydrated` before deciding)
- AdminRoute is hydration-aware (same pattern)
- All pages use `AppLayout` (TopNav + scrollable main)
- Do NOT touch models unless noted

---

## 1 — Accounts

### What exists
- `LoginPage` — split panel (brand left, form right), email/username field, error handling
- `ProfilePage` — personal info, integrations (Jira/GitHub), notifications, change password
- `UsersPage` — paginated table, create/edit/delete modals, team dropdown
- `TeamsPage` — left panel list (paginated), right panel members + settings tabs
- `TopNav` — dropdown with Profile + admin links (role-gated) + sign out
- `authStore` — bootstrap, hydration, sessionExpired, clearSession
- `ProtectedRoute` — hydration-aware, passes sessionExpired reason to /login
- `AdminRoute` — hydration-aware, non-admins → /projects

### What is missing / broken
1. **LoginPage ignores `sessionExpired` reason** — location state carries `reason: "expired"` from ProtectedRoute but LoginPage never reads it and shows no message
2. **Hydration blank flash** — ProtectedRoute returns `null` while `!hasHydrated`, causing a white screen on refresh. Needs a fullscreen spinner
3. **`UserProfile` type gap** — `auth.ts::UserProfile` only has `primary_team` + `organization_role` + `notification_provider`. But `ProfilePage::syncCurrentUserProfile` writes `organization_name`, `team_name`, `team_memberships`, `notifications_enabled`, `created_at` onto it. TypeScript won't complain at runtime but the type contract is wrong
4. **`canCreateProject` excludes managers** — ProjectsPage only allows `platform_owner` / `org_admin`. Backend allows team managers (members with manager role) to create projects too — confirmed

### What to improve (design / UX)
- LoginPage: show "session expired" notice when redirected from a protected route
- Add a fullscreen loading state during hydration (replaces the null flash)
- Fix UserProfile type to match what the store actually holds post-bootstrap

### Backend endpoints used
All existing, no new endpoints needed for accounts phase.

### No backend changes needed for accounts ✅

---

## 2 — Projects

### What exists
- `ProjectsPage` — grid, create modal, role-gated "New Project" button (bug: excludes managers)
- `ProjectWorkspacePage` — two-panel: tree sidebar + case detail panel
- `ProjectTree` — suite → section → scenario tree, lazy case loading
- `TestCaseDetailPanel` — breadcrumb, badges, steps table, spec links

### What is missing
- Manager role cannot create projects (frontend bug, backend allows it)
- No edit/delete project from projects list
- No project member management UI
- Tree is read-only (no CRUD: create/rename/delete suite, section, scenario, case)
- No automation view inside workspace

### Backend endpoints available
- `GET/POST /api/projects/` — list + create
- `GET/PATCH/DELETE /api/projects/:id/` — detail, update, delete
- `GET /api/projects/:id/tree/` — full tree
- `GET/POST /api/projects/:id/members/` — project membership
- `PATCH/DELETE /api/projects/:id/members/:id/` — update/remove member

### Possible new endpoint
- `GET /api/projects/:id/` — should return team_name on the project serializer if not already (check)

---

## 3 — Specifications

### What exists
- **Nothing in frontend** — zero pages, zero API layer

### Backend endpoints available (from prior backend work)
- `POST /api/specs/upload/` — upload spec file (PDF/Word/text)
- `GET /api/specs/` — list specs for a project
- `GET /api/specs/:id/` — spec detail + chunks
- `DELETE /api/specs/:id/` — delete spec
- Chunk traceability endpoints (link spec chunk → test case)

### Plan
- SpecsPage inside project workspace (new tab/section)
- Upload UI (drag & drop or file picker)
- Spec list with chunk preview
- Traceability: link chunks to test scenarios/cases

---

## 4 — Testing

### What exists
- `ProjectTree` — full read-only tree (suite → section → scenario → case)
- `TestCaseDetailPanel` — case detail view

### What is missing
- Create/edit/delete suite from tree
- Create/edit/delete section from tree
- Create/edit/delete scenario from tree
- Create/edit/delete test case (full form: steps, preconditions, expected result)
- Test case status management

### Backend endpoints
- `GET/POST /api/testing/suites/` — suites CRUD
- `GET/POST /api/testing/sections/` — sections CRUD
- `GET/POST /api/testing/scenarios/` — scenarios CRUD
- `GET/POST /api/testing/cases/` — cases CRUD
- All have PATCH/DELETE variants

---

## Implementation order

```
1. Accounts — polish pass (session expired, hydration flash, type fix, manager create)
2. Projects — manager create fix, then project member management
3. Specifications — upload + list + traceability
4. Testing — tree CRUD (create/edit/delete inline)
```

---

## Do not touch unless needed

- All models (UserProfile, Team, Project, TestSuite, TestSection, TestScenario, TestCase, Spec, SpecChunk)
- Existing service layer logic
- Existing permissions/access service functions
- Token storage mechanism (biat_access / biat_refresh)
- The bootstrap/hydration pattern in authStore

---

## Risks / dependencies

- Specifications frontend depends on knowing exact spec serializer shape — read before building
- Testing CRUD depends on understanding section parent FK + scenario ordering — read before building
- `UserProfile` type mismatch could cause silent data inconsistency in TopNav after profile save — fix before moving to projects
