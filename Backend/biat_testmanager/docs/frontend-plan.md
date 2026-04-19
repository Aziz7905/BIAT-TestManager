# Frontend Plan

## Current Status

### Accounts
- Auth bootstrap and session-expiry handling are implemented.
- Existing screens: login, profile, users admin, teams admin.
- Current work: finish the Accounts slice by aligning the frontend with backend response shapes, using the shared shell consistently, and making admin workflows complete against paginated APIs.
- Backend endpoints already usable:
  - `POST /api/login/`
  - `POST /api/logout/`
  - `POST /api/refresh/`
  - `GET /api/me/`
  - `GET/PATCH /api/profile/`
  - `POST /api/profile/change-password/`
  - `GET/POST/PATCH/DELETE /api/admin/users/`
  - `GET/POST/PATCH/DELETE /api/teams/`
  - `GET/POST/PATCH/DELETE /api/teams/<id>/members/`
- No backend additions are planned for this slice.

### Projects
- Existing screens: projects list, project workspace tree, test case detail panel.
- Missing: richer project create/edit/member workflows, reporting entry points, and cleaner team selection.

### Specifications
- Frontend is mostly still missing.
- Backend is ready for source list/detail, parse, import, and specification list/detail workflows.

### Testing
- Frontend is mostly still missing outside the project workspace tree and case detail.
- Backend already supports repository authoring, revisions, runs, plans, and reporting.

## Implementation Order
1. Accounts
2. Projects
3. Specifications
4. Testing

## Accounts Work In Progress
- Put profile and admin pages into the shared app shell.
- Align account types with backend fields such as `team`, `team_name`, and `team_memberships`.
- Make admin users and teams workflows handle paginated backend responses instead of silently showing only the first page.
- Keep backend models out of scope unless a real UI blocker appears.

## Risks And Dependencies
- The frontend must follow backend response shapes exactly; old field names like `primary_team` are contract drift now.
- Shared UI component APIs must stay stable before broader page work continues.
- Local Vite/Tailwind native dependency issues can block full builds even when TypeScript passes.

## Do Not Touch Unless Needed
- Backend models in `accounts`, `projects`, `specs`, and `testing`
- Backend permission and service-layer logic
- Frontend styling system or component library structure beyond small shared utilities with real reuse
