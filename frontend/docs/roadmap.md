# Frontend Roadmap

**The frontend build order. Aligned with backend phases.**

---

## How to read this document

Each step is a self-contained slice of work that:
- Depends on a backend capability being live (or already exists)
- Ships one or more user-visible improvements
- Does not block other tracks

Steps are sequenced by priority + backend dependency. Don't ship a frontend feature before its backend phase is live.

---

## Where we are

### What works today
- Auth: login, hydration, silent refresh, role-based redirects
- Admin: users + teams CRUD with paginated lists
- Project list + create
- Project workspace shell + tab routing
- Repository tree (read + most CRUD), test case editor with structured steps
- Spec intake / record review / specification browser (functional, UX still rough)
- Automation workspace: trigger execution, live step timeline, noVNC stream, full-screen live page, checkpoint resume modal
- Test runs workspace: plans / runs / run-cases panels (read + manual status)

### Known issues
- noVNC canvas sizing inconsistent for script executions (vs manual browser sessions)
- Test Runs ↔ Execution wiring is partially present, but the run-case status/navigation flow still needs verification and polish
- Reporting dashboard is a skeleton (endpoints exist, UI doesn't)
- `run_kind` filter not yet wired in Test Runs tab

### Not built
- AI test generation UI
- AI script generation UI
- Live agent view
- Self-healing review queue
- RCA panel

---

## The build order

```
Step 0 — Restore Teams admin page API compatibility (done in current branch)
Step 1 — noVNC sizing fix
Step 2 — Test Runs ↔ Execution wiring
Step 3 — run_kind filter
Step 4 — Reporting dashboard
Step 5 — Specs UX polish
Step 6 — Stream policy in UI (Watch this run, Debug Rerun)
Step 7 — RCA panel (Phase D backend dependency)
Step 8 — AI test generation review queue (Phase D)
Step 9 — Live agent view (Phase E)
Step 10 — Healing review queue (Phase F)
```

---

## Step 0 — Restore Teams admin page API compatibility

**Status:** done in the current branch; `Team` types and the Teams admin detail panel no longer read removed `Team.tokens_used_this_month`.

### Why now
This was a regression from the backend schema cleanup. The Teams admin page expected fields that were moved out of `Team`, so admin/team configuration work could be blocked before the AI configuration surfaces were reachable.

### What changes
- Update frontend `Team` types to match the current backend serializer
- Remove direct reads of deprecated fields such as `tokens_used_this_month`
- If token budget usage is still needed in the UI, read it from the dedicated team AI configuration endpoint/shape instead of `Team`

### Definition of done
`/admin/teams` loads again, team details render without runtime crashes, and the page no longer depends on removed `Team` fields.

---

## Step 1 — noVNC sizing fix

### Why now
The cleanest user-facing improvement on the existing stack. Manual browser sessions render correctly; script executions don't. Closing the parity gap removes a confusing inconsistency.

### What changes
- Investigate the size mismatch between manual sessions and script executions
- Likely cause: layout settles late on script execution mount; the resize-trigger workaround needs to fire on a different event
- Fix the observed mismatch
- Add a regression test if possible (visual regression screenshot)

### Definition of done
A script execution's noVNC viewer renders at the same dimensions as a manual session in the same panel.

---

## Step 2 — Test Runs ↔ Execution wiring

### Why now
The biggest current functional gap — Test Runs and Automation are disconnected. A user looking at a run can't see whether automated cases passed or failed.

### What changes
- Backend: ensure `TestRunCase` exposes a link to its most recent `TestExecution`
- Frontend: in the Run Cases pane, render execution-derived status when present
- Click on a run case → navigate to its latest execution detail
- Manual status dropdown remains for non-automated cases

### Definition of done
Inside a run, automated cases show pass/fail from their execution. Failed cases link directly to the failing execution.

---

## Step 3 — `run_kind` filter

### Why now
`run_kind` exists on the backend. The Test Runs tab shows everything including `system_generated` runs, which clutter the view (those are AI/ad-hoc executions, not user-initiated).

### What changes
- Default Test Runs filter: `run_kind ∈ {planned, standalone}`
- Toggle to show/hide `system_generated`
- Visual badge on each run showing its kind

### Definition of done
The Test Runs tab is uncluttered by default, with an option to expose the system-generated runs.

---

## Step 4 — Reporting dashboard

### Why now
Endpoints exist (`/reporting/overview`, `/pass-rate-trend`, `/failure-hotspots`). The frontend hasn't surfaced them.

### What changes
- `DashboardPage` becomes a real page
- Top: summary cards (total runs this week, pass rate, failure rate, recent activity)
- Middle: pass-rate trend chart (line chart over the last 30 days)
- Bottom: failure hotspots (top 10 most failure-prone test cases)
- Project filter (default: all user's projects)

### Definition of done
A user can open the dashboard and see their team's QA health at a glance.

---

## Step 5 — Specs UX polish

### Why now
Specs work but are rough. Improvements compound when AI generation lands (Step 8) — clean specs flow → clean AI inputs.

### What changes
- Better source upload UX (drag-and-drop, progress indicator)
- Cleaner record review UI (side-by-side: source content + extracted record)
- Traceability-first detail panels: "this spec is referenced by N test cases"
- Bulk approve/reject of records
- Clearer indexing status with retry button on failure

### Definition of done
A QA tester can ingest a 50-page PDF spec and review records end-to-end without confusion.

---

## Step 6 — Stream policy in UI

### Why now
Backend Step 3 (Selenoid + runners + MinIO + stream policy) introduces `stream_enabled` and `debug_rerun` fields. Frontend needs to expose them.

### What changes

**"Watch this run live" checkbox:**
- In every "Run" / "Trigger execution" dialog
- Default: unchecked (silent execution)
- Checked → API call sets `stream_enabled=true`
- After trigger, navigate to the execution and auto-open noVNC

**"Debug Rerun" button:**
- Appears on every failed `TestExecution` detail
- Click → POST to `/api/test-executions/<id>/debug-rerun/`
- Receives new execution id
- Navigate to it; auto-open noVNC

**Default execution detail behavior:**
- Open event stream WebSocket (cheap, useful)
- Open noVNC WebSocket only if `execution.stream_enabled === true`

### Definition of done
- Triggering a regression run with default settings does NOT open a noVNC stream
- Triggering with "Watch this run" DOES open a noVNC stream
- Debug rerun creates a new streamed execution and auto-opens noVNC

---

## Step 7 — RCA panel (Phase D — first AI feature on the frontend)

### Why now
Backend Step 7 (Phase D — RCA/offline generation) ships this capability. Smallest AI feature, biggest immediate user value. Prepares the team's AI plumbing.

### What changes
- Add a markdown renderer dependency (likely `react-markdown`)
- On any failed `TestExecution` detail with `result.ai_failure_analysis`:
  - Render the RCA in a styled panel below the error
  - Subscribe to the `rca_ready` WebSocket event for live arrival
- "Create Jira bug" button (depends on backend integration adapter)

### Definition of done
A user looking at a failed execution sees a human-readable AI explanation of why it failed, and can create a Jira bug from it in one click.

---

## Step 8 — AI test generation review queue (Phase D)

### Why now
Backend Step 7 (Phase D) ships test generation and script generation. Frontend needs to expose the triggers and the review flow.

### What changes

**Triggers (in-context):**
- "Generate tests from this spec" button on the Specifications tab
- "Generate Selenium script from this case" button in the Test Case editor. Default generated script target is Selenium Java; Selenium Python remains selectable for prototypes/existing scripts.
- "Generate from Jira ticket" button on the Specifications tab (offline mode)

**Review queue (new AI tab):**
- New tab in the workspace: "AI"
- Pending candidates list (TestCases + AutomationScripts)
- Filter by type, by source
- Review modal:
  - View / edit the candidate
  - See the source context (Jira excerpt, spec chunks)
  - Approve / Approve with edits / Reject

**Notifications:**
- Toast on completion
- Badge on the AI tab when items are pending

### Definition of done
A user can:
1. Click "Generate" on a spec
2. See "Generation in progress"
3. Get notified when complete
4. Open the review queue
5. Approve a candidate
6. The approved candidate is now a canonical `TestCase` in the repository

---

## Step 9 — Live agent view (Phase E)

### Why now
Backend Step 5 (Phase E — LangGraph live agent) ships. The headline product experience.

### What changes

**Agent launcher:**
- "Author with agent" button in the AI tab
- Modal: natural-language description, optional source context (spec / Jira), target URL

**Live agent view (new route):**
- `/projects/:id/ai/sessions/:sessionId`
- Two columns: noVNC viewer (always streaming) + agent narration timeline
- New WebSocket event types: `agent_thought`, `agent_decision`, etc.
- Pause / Take over / Cancel buttons
- "Take over" enables bidirectional input on noVNC

**Session history:**
- List of past agent sessions
- Replay (video + narration)

### Definition of done
A user can start an agent session, watch the agent work, take over if needed, and end up with a candidate `TestCase` + `AutomationScript` ready for review.

---

## Step 10 — Healing review queue (Phase F)

### Why now
Backend Step 9 (Phase F — Self-healing) ships. Last major AI surface.

### What changes
- Pending healing events list
- For each event: failed selector, candidate fixes with confidence, original screenshot
- Apply / Reject / Manual fix buttons
- Auto-apply happens server-side; this UI is for low-confidence escalations

### Definition of done
When a regression run fails on a selector and the agent's proposed fix is below auto-threshold, the user sees a clear review surface and can resolve in one click.

---

## What's NOT on the roadmap

| Feature | Why deferred |
|---|---|
| Mobile-responsive design | Bank QA users work on desktops; mobile not a primary target |
| Dark mode | Office daytime use; complexity not justified |
| Cross-project analytics dashboard | Workspace-first IA; per-project dashboards are sufficient |
| Real-time collaboration (multiple users editing the same case) | Bank workflows are mostly sequential; not worth the complexity |
| Notification center / inbox | Email/Slack/Teams already configured per user; in-app inbox would duplicate |
| Native performance/security/API runner UIs | Browser E2E is the owned execution lane; other categories stay managed/ingested until backend engines exist |

These are not "future phases" — they're decisions to not pursue them within the current product vision.

---

## How to keep this current

- When a step ships, update its section to "Shipped on YYYY-MM-DD" and move it to a "Completed" history section at the bottom
- Don't delete shipped steps — they're useful as a project log
- New mid-stream needs: insert a step with the right number (e.g., 4.5) without renumbering everything
