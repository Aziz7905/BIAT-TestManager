# Frontend — Current State

## Stack

- **Vite** + **React 19** + **TypeScript**
- **Tailwind CSS v4** (via `@tailwindcss/vite` plugin — no PostCSS needed)
- **React Router v7** (BrowserRouter)
- **Zustand v5** (auth state)
- **Axios v1** (HTTP client with JWT interceptor)

## Directory Layout

```
frontend/
  src/
    index.css               # Tailwind import + CSS custom property tokens
    main.tsx                # React entry point
    App.tsx                 # Thin wrapper → AppRouter

    types/
      auth.ts               # User, UserProfile (primary_team, organization_role), LoginResponse, RefreshResponse
      accounts.ts           # PaginatedResponse<T>, OrganizationRole, TeamMembershipRole, NotificationProvider, MyProfile, AdminUser, Team, TeamMember + payloads
      testing.ts            # ProjectTree, TestSuite, TestSection, TestScenario, TestCase

    api/
      client.ts             # Axios instance + JWT request/refresh interceptors
      accounts/
        auth.ts             # login(), logout(), getMe()
        profile.ts          # getMyProfile(), updateMyProfile(), changeMyPassword()
        users.ts            # getUsersPage(), getAllUsers(), createUser(), updateUser(), deleteUser()
        teams.ts            # getTeamsPage(), getAllTeams(), getTeamMembersPage(), createTeam(), updateTeam(), deleteTeam(), addTeamMember(), updateTeamMember(), removeTeamMember()
      projects/
        projects.ts         # getProjects(), createProject(), getProjectTree()
      testing/
        cases.ts            # getCasesForScenario()

    store/
      authStore.ts          # Zustand: user, accessToken, isAuthenticated, login/logout
                            # login() throws on failure — component handles error display

    router/
      ProtectedRoute.tsx    # Passes location state for post-login redirect
      AppRouter.tsx         # Routes: /login, /projects, /projects/:id, /profile, /admin/users, /admin/teams
                            # AdminRoute guard: waits for hasHydrated, redirects non-admins to /projects

    pages/
      LoginPage.tsx         # Split-panel: white left (brand+video), white right (form card)
                            # Redirects: org_admin/platform_owner → /admin/users, else → /projects
      ProfilePage.tsx       # Personal info, integrations (Jira/GitHub tokens), notifications, change password
                            # Syncs updated name/role back into authStore on save
      ProjectsPage.tsx      # Grid of project cards + create modal
      ProjectWorkspacePage.tsx  # Two-panel: tree sidebar (256px) + detail panel
      admin/
        UsersPage.tsx       # Paginated user table, create/edit/delete modals, team dropdown
        TeamsPage.tsx       # Left panel: team list with pagination; right panel: Members tab + Settings tab
                            # Members: add member (UserPicker), inline role change, remove
                            # Settings: name, manager picker, AI config, integrations

    components/
      ui/
        Button.tsx          # variant, size, isLoading, loadingText props
        Input.tsx
        ErrorMessage.tsx    # Dismissible, with warning icon
        Badge.tsx
        Modal.tsx
        PageHeader.tsx
        Spinner.tsx
        EmptyState.tsx
        UserPicker.tsx        # Search-filtered user dropdown (name/email), used in team create + add-member
        index.ts
      project/
        ProjectTree.tsx     # Full suite→section→scenario→case tree with expand/collapse
        TestCaseDetailPanel.tsx  # Breadcrumb, badges, steps table, spec links
```

## Authentication Flow

1. User submits credentials → `POST /api/login/` with `{ identifier, password }`
2. Response: `{ access, refresh, user }` stored in `localStorage` via `tokenStorage`
3. Axios request interceptor attaches `Authorization: Bearer <access>` on every call
4. On 401: response interceptor tries `POST /api/refresh/` with `{ refresh }`
   - Success → update `biat_access` in localStorage, retry original request
   - Fail → clear tokens, redirect to `/login`
5. Logout: `POST /api/logout/` with `{ refresh }` (blacklists token), then clear store

**Token keys in localStorage:**
- `biat_access` — JWT access token
- `biat_refresh` — JWT refresh token

## Role-Based Routing

| Role | Post-login redirect |
|------|-------------------|
| platform_owner | `/admin/users` |
| org_admin | `/admin/users` |
| member | `/projects` |

## Design System

Custom Tailwind tokens defined as CSS variables in `index.css → :root`:

| Token | Value (RGB) | Usage |
|---|---|---|
| `primary` | 37 99 235 | blue-600 — CTA, links |
| `primary-light` | 219 234 254 | blue-100 — backgrounds |
| `surface` | 255 255 255 | card/panel backgrounds |
| `bg` | 248 250 252 | page background |
| `warm` | 234 88 12 | orange-600 — warnings |
| `text` | 15 23 42 | slate-900 — body text |
| `muted` | 100 116 139 | slate-500 — secondary |
| `border` | 226 232 240 | slate-200 — borders |

Font: **Plus Jakarta Sans** (declared in `tailwind.config.ts`, falls back to system-ui).

## Backend API Endpoints Used

### Auth
| Method | Path | Purpose |
|---|---|---|
| POST | /api/login/ | Get access + refresh + user |
| POST | /api/logout/ | Blacklist refresh token |
| POST | /api/refresh/ | Rotate access token |
| GET | /api/me/ | Current user + profile |

### Profile (all users)
| Method | Path | Purpose |
|---|---|---|
| GET | /api/profile/ | Full profile (org, team memberships, integration flags, notification settings) |
| PATCH | /api/profile/ | Update: first_name, last_name, jira_token, github_token, notification_provider, slack/teams IDs, notifications_enabled |
| POST | /api/profile/change-password/ | current_password + new_password |

**Profile response shape:** id, first_name, last_name, email, organization_name, organization_role, team (uuid), team_name, team_memberships[], has_jira_token, has_github_token, notification_provider, notifications_enabled, slack_user_id, slack_username, teams_user_id, has_slack_user, has_teams_user

### Admin — Users (platform_owner + org_admin)
| Method | Path | Purpose |
|---|---|---|
| GET | /api/admin/users/ | Paginated user list scoped to actor |
| POST | /api/admin/users/ | Create user: first_name, last_name, password, team (uuid), team_membership_role, organization_role, is_staff |
| GET | /api/admin/users/:id/ | User detail |
| PATCH | /api/admin/users/:id/ | Update: same fields, password optional |
| DELETE | /api/admin/users/:id/ | Delete (platform_owner row rejected by backend) |

**User response shape (AdminUserSerializer):** id, username, email, first_name, last_name, is_staff, is_superuser, profile (nested UserProfileSerializer), date_joined

### Admin — Teams (platform_owner + org_admin; managers see own team only)
| Method | Path | Purpose |
|---|---|---|
| GET | /api/teams/ | List teams scoped to actor |
| POST | /api/teams/ | Create team: name, manager (user id), ai_provider, ai_api_key, ai_model, monthly_token_budget, jira_base_url, jira_project_key, github_org, github_repo, jenkins_url |
| GET | /api/teams/:id/ | Team detail |
| PATCH | /api/teams/:id/ | Update team (managers limited to AI/integration fields only) |
| DELETE | /api/teams/:id/ | Delete team |
| GET | /api/teams/:id/members/ | List active memberships |
| POST | /api/teams/:id/members/ | Add member: user (int id), role, is_primary |
| PATCH | /api/teams/:id/members/:mid/ | Update membership: role, is_primary |
| DELETE | /api/teams/:id/members/:mid/ | Remove member |

**Team response shape (TeamSerializer):** id, organization (uuid), organization_name, name, manager (int), manager_name, member_names[], member_count, ai_provider, ai_provider_name, has_ai_api_key, ai_model, monthly_token_budget, tokens_used_this_month, jira_base_url, jira_project_key, github_org, github_repo, jenkins_url, created_at

**TeamMember response shape (TeamMemberSerializer):** id, user_id, first_name, last_name, full_name, email, user_role (org role), role (team role), is_primary, is_active, joined_at

### Projects
| Method | Path | Purpose |
|---|---|---|
| GET | /api/projects/ | Paginated project list (handles both paginated and plain array) |
| POST | /api/projects/ | Create project |
| GET | /api/projects/:id/tree/ | Full suite→section→scenario tree (cases load lazily) |

### Testing
| Method | Path | Purpose |
|---|---|---|
| GET | /api/testing/scenarios/:id/cases/ | Cases for a scenario (lazy load on expand) |

## Build Status

- Phase 1 ✅ — Auth foundation (login, token management, protected routes)
- Phase 2 ✅ — Projects list page (grid, create modal, paginated response guard)
- Phase 3 ✅ — Project workspace + tree sidebar (suite→section→scenario→case hierarchy)
- Phase 4 ✅ — Test case detail panel (breadcrumb, badges, steps table, spec links)
- Phase 5 ✅ — Accounts app: Profile page, Admin Users, Admin Teams
- Phase 6 🔲 — Tree CRUD (create/edit/delete from tree context menu)
- Phase 7 🔲 — Automation: run execution + live streaming
- Phase 8 🔲 — Reporting dashboard
- Phase 9 🔲 — Specs upload + traceability

## Key Quirks / Gotchas

- DRF returns `{ count, next, previous, results[] }` — use `Array.isArray(data) ? data : data.results` guard
- Login `identifier` field accepts email OR username (not separate fields)
- `ProjectTree` type from `../types/testing` clashes with component name — import as `ProjectTreeData`
- React 19: don't use `FormEvent` — use `{ preventDefault(): void }` inline type on handlers
- Button component uses `isLoading` + `loadingText` props (not `loading`)
- Tree response includes suites→sections→scenarios with `case_count`, cases load lazily via separate endpoint
- `PaginatedResponse<T>` is defined in `types/accounts.ts` and re-used across API helpers
- `getAllUsers()` / `getAllTeams()` walk all pages — use for pickers; use `getUsersPage(n)` for tables
- `AdminRoute` in AppRouter checks `hasHydrated` before redirecting to avoid flash on reload
- `ProfilePage` calls `syncCurrentUserProfile()` after save to keep TopNav initials/name in sync
