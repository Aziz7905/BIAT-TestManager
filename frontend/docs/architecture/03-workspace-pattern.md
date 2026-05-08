# 03 — Workspace Pattern

**The tabbed workspace. Tree + detail pane. Modal vs route. The IA philosophy.**

---

## 1. The IA principle: workspace, not pages

The platform's IA is intentionally **workspace-first**, not page-sprawl.

### 1.1 What workspace-first means
Inside a project, the user does most of their work in **one tabbed view** (`/projects/:id`). Tabs swap the body content. The project header stays in place. The user keeps their context.

### 1.2 What we explicitly avoid
- A top-level `/test-cases` page that shows test cases from every project
- A top-level `/executions` page that shows every execution
- A top-level `/specs` page
- Any URL of the form `/<resource>` (without a project scope)

These would force the user to add a project filter every time. Worse, they'd encourage cross-project queries that don't match how the bank's QA team actually works.

### 1.3 How the user thinks
> *"I'm working on the Banking App today."*

Not:
> *"Today I'll spend the morning in the Test Cases module across all my projects."*

The IA reflects the first sentence.

---

## 2. The tabbed workspace structure

```
┌─────────────────────────────────────────────────────────────┐
│  TopNav (logo, profile menu, admin link if applicable)     │
├─────────────────────────────────────────────────────────────┤
│  PROJECT HEADER                                             │
│  ┌─────┐  Banking App                  [Members] [Settings] │
│  │ icon│  team: QA Team · members: 5 · status: active      │
│  └─────┘                                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ [Repository*] [Specifications] [Test Runs] [Auto..] │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                ACTIVE TAB CONTENT                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

The active tab is reflected in the URL (e.g., `/projects/<id>?tab=automation`). Bookmarks and refreshes preserve the tab.

---

## 3. The four tabs (current) + planned AI tab

### 3.1 Repository (default)
**Pattern:** tree on the left, detail pane on the right.

```
┌─────────────────────┬─────────────────────────────────────┐
│  PROJECT TREE        │  DETAIL PANE                        │
│                      │                                     │
│  ▼ Suite: Auth       │  TestCase: "User can login..."      │
│    ▼ Section: Login  │                                     │
│      ▼ Scenario: ... │  Status: approved                   │
│        • TC: User... │  Linked specs: 2                    │
│        • TC: Bad...  │  Steps: (rendered)                  │
│      ▶ Scenario: ... │                                     │
│    ▶ Section: Signup │  [Edit case] [Approve] [Archive]    │
│  ▶ Suite: Transfers  │                                     │
└─────────────────────┴─────────────────────────────────────┘
```

- Tree is virtualized; cases load lazily on scenario expand
- Detail pane is **entity-aware**: clicking a suite shows the suite overview, clicking a scenario shows scenario details, clicking a case shows the case
- Editing the case opens a **modal**, not an inline replacement of the detail pane
- Tree CRUD (add suite, add section, rename, delete) via context menu on tree nodes

### 3.2 Specifications
**Pattern:** list of sources on the left, detail/review on the right.

```
┌─────────────────────┬─────────────────────────────────────┐
│  SOURCES             │  SOURCE DETAIL / RECORDS            │
│                      │                                     │
│  ▶ regulatory.pdf    │  Source: regulatory.pdf             │
│    parsed (45 recs)  │  Records: 45                        │
│  ▶ user-stories.csv  │                                     │
│    pending review    │  Record #12 (pending review)        │
│  ▶ jira: PROJ-123    │  Content: "User must..."            │
│                      │  [Edit] [Approve] [Reject]          │
│                      │                                     │
│  + Upload source     │                                     │
│                      │                                     │
└─────────────────────┴─────────────────────────────────────┘
```

- Sources show their parser status
- Pending records require approval before becoming canonical
- Approved → automatic indexing for RAG (status badge updates)
- Imported `Specification` browser is a separate sub-view

### 3.3 Test Runs
**Pattern:** three-pane: Plans → Runs → Run Cases.

```
┌─────────────┬─────────────────┬───────────────────────────┐
│  PLANS       │  RUNS            │  RUN CASES                │
│              │                  │                           │
│  ▶ Sprint 23 │  ▶ Smoke 23-1   │  TC #1: Login → passed   │
│    3 runs    │    50 cases     │  TC #2: Logout → passed  │
│  ▶ Sprint 22 │    pass: 47/50  │  TC #3: Bad pwd → failed │
│              │  ▶ Regression  │  TC #4: ...               │
│              │    100 cases    │                           │
│  + New plan  │                  │  [Bulk action] [Export]  │
│              │  + New run       │                           │
└─────────────┴─────────────────┴───────────────────────────┘
```

- Default filter: `run_kind ∈ {planned, standalone}` (hides system_generated)
- Run cases show their pinned `test_case_revision` and current status
- A failed run case → user can navigate to the failed `TestExecution` for live/replay

### 3.4 Automation
**Pattern:** sidebar list of recent executions, main area with browser + step timeline.

```
┌──────────────┬──────────────────────────────────────────────┐
│ EXECUTIONS    │  BROWSER PANEL (noVNC if streaming)         │
│               │                                              │
│ ▶ Exec 4523   │  ┌────────────────────────────────────┐    │
│   running     │  │                                    │    │
│ ▶ Exec 4522   │  │   [browser pixels via noVNC]       │    │
│   passed      │  │                                    │    │
│ ▶ Exec 4521   │  │   (off when stream_enabled=False)  │    │
│   failed      │  └────────────────────────────────────┘    │
│               │                                              │
│ + Run script  │  STEP TIMELINE                              │
│               │  ✓ Step 1: open URL          1.2s           │
│               │  ✓ Step 2: enter username    0.3s           │
│               │  ✗ Step 3: click submit      ERROR          │
│               │     "no element matches #submit"            │
│               │                                              │
└──────────────┴──────────────────────────────────────────────┘
```

- Sidebar shows recent executions for this project
- Selecting an execution loads its details into the main area
- For running executions with `stream_enabled=True`: noVNC viewer + live step timeline
- For completed executions: video replay + final step timeline + result panel
- "Watch this run" button — sets `stream_enabled=True` before triggering
- "Debug Rerun" on failed runs — creates a new streamed execution

### 3.5 AI tab (planned, Phase D + E)
**Pattern:** review queue + agent launcher + history.

```
┌──────────────────────────────────────────────────────────┐
│  REVIEW QUEUE                                             │
│  ▶ AI-generated TestCase: "User can recover password"    │
│    (from Jira ticket PROJ-456)         [Review] [Reject] │
│  ▶ AI-generated AutomationScript for TC #234            │
│                                          [Review] [Reject]│
├──────────────────────────────────────────────────────────┤
│  AGENT LAUNCHER                                           │
│  [Author with agent] [Validate from Jira] [Validate PR]  │
├──────────────────────────────────────────────────────────┤
│  AGENT SESSION HISTORY                                    │
│  ▶ 2026-05-07 10:23 — generated 3 cases from PROJ-456    │
│  ▶ 2026-05-07 09:15 — validated PR #1234                 │
└──────────────────────────────────────────────────────────┘
```

See [`05-ai-ux.md`](05-ai-ux.md) for full details.

---

## 4. Modal vs route

### 4.1 The rule
- **Modals** for editing operations that should not lose the surrounding context
- **Routes** for full-screen views that have their own URL semantics

### 4.2 What's a modal
- Test case editor (opens with case context, full structured editor)
- Test scenario edit
- Suite/section create
- Confirm dialogs
- Project members management
- Specification source record edit/approve

### 4.3 What's a route
- The full-screen live execution view (`/projects/:id/automation/.../live`)
- The login page
- The admin pages
- Profile

### 4.4 Why this split
Modals preserve the user's context. Editing a test case shouldn't navigate away from the tree — when the user closes the modal, they're back where they were. Routes are for things that *replace* the workspace temporarily (full-screen execution view) or aren't part of the workspace (admin).

---

## 5. The detail pane is read-first

Inside the Repository tab, the right panel is a **read view** by default. Editing happens in a modal launched from the read view.

**Why:**
- The user spends most time reading, not editing
- Read-first surfaces are simpler — they show data without form complexity
- Modal-based editing is a clearer mental model: "I'm now editing this thing in a focused window"
- It avoids the "implicit save / explicit save" ambiguity of inline editing

---

## 6. URL state in the workspace

The active tab is in the URL:
```
/projects/<id>?tab=repository
/projects/<id>?tab=automation
```

Selected entities (selected suite, selected case) are also in the URL where useful:
```
/projects/<id>?tab=repository&suite=<suite-id>&case=<case-id>
```

This makes:
- Refresh-safe — the tab and selection survive a reload
- Shareable — you can copy a URL and send it to a colleague who has the same project access
- Deep-linkable — emails / Slack messages can link directly to a specific case

---

## 7. Cross-project navigation

There is no top-level "switch project" widget. The user navigates:
1. Click logo / "Projects" in TopNav
2. Land on `/projects` (the project list)
3. Click another project
4. Land on `/projects/<other-id>`

This is more clicks than a project picker but enforces the "one project at a time" mental model. A project picker would invite the question *"can I see things from multiple projects at once?"* — and the answer is no.

If usage data later shows users wanting fast project-switching, add a project picker in the TopNav as a Phase E+ enhancement. Don't preemptively add it.

---

## 8. Pagination handling

DRF returns `{ count, next, previous, results[] }` for all list endpoints. Page size default: 50.

The frontend uses a guard everywhere:
```typescript
const items = Array.isArray(data) ? data : data.results;
```

This handles both paginated and (rare) plain-array responses uniformly. List components have a `<PaginationControls>` companion that calls `getXPage(pageNumber)`.

Pickers (e.g., user picker for adding a team member) use `getAllX()` walks-all-pages helpers — fine when the count is small (<500). For larger collections, switch to a search-as-you-type endpoint with debouncing.

---

## 9. Page anatomy: a typical workspace page

`ProjectWorkspacePage` is built like this:

```tsx
function ProjectWorkspacePage() {
  const { id } = useParams();
  const [tab, setTab] = useTabFromQueryString();
  const [project, setProject] = useState(null);

  useEffect(() => {
    api.projects.get(id).then(setProject);
  }, [id]);

  if (!project) return <Spinner />;

  return (
    <AppLayout>
      <ProjectHeader project={project} />
      <TabBar tab={tab} onTabChange={setTab} />
      {tab === 'repository' && <RepositoryTab projectId={id} />}
      {tab === 'specifications' && <SpecificationsTab projectId={id} />}
      {tab === 'test-runs' && <TestRunsTab projectId={id} />}
      {tab === 'automation' && <AutomationTab projectId={id} />}
      {/* Phase D+: */}
      {tab === 'ai' && <AITab projectId={id} />}
    </AppLayout>
  );
}
```

Each tab is its own component, fetches its own data, manages its own state. They share nothing except the project id.

This composition pattern keeps each tab independently testable and prevents one tab's complexity from leaking into another.
