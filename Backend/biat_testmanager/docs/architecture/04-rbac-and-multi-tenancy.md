# 04 — RBAC and Multi-Tenancy

**The 3-layer authorization model. Multi-tenant data isolation. Concurrency groups. The team workflow scenario walkthrough.**

---

## 1. The three authorization layers

Every API call is checked against three layers, in this order:

```
1. Organization role  (UserProfile.organization_role)
       ↓
2. Team role          (TeamMembership.role)
       ↓
3. Project role       (ProjectMember.role)
```

If any layer denies, the request is denied. A user is "allowed" only when all relevant layers permit.

### 1.1 Organization role
| Role | Power |
|---|---|
| `platform_owner` | Manages the platform itself. Can create organizations. Cannot be deleted by the API. |
| `org_admin` | Full access within their organization. Manages teams, users, billing. |
| `member` | Standard user. Authority comes from team and project memberships. |

### 1.2 Team role (`TeamMembership.role`)
| Role | Power |
|---|---|
| `manager` | Configures team AI provider, integrations, manages team members, creates projects |
| `member` | Works on projects they're added to |
| `viewer` | Read-only across team's projects |

**`Team.manager`** is a UI display pointer only. Authority for "managing this team" comes from `TeamMembership(role='manager')`. Several users can be team managers concurrently.

### 1.3 Project role (`ProjectMember.role`)
| Role | Power |
|---|---|
| `manager` | Configures project, manages members, archives project, sees all data |
| `member` | Standard contributor — creates/edits cases, runs tests, reviews AI output |
| `viewer` | Read-only access to project data |

A team manager has implicit project-level authority on every project in their team. They don't need to be added as a project member.

---

## 2. Why three layers (not just one)

A flat `is_admin` flag wouldn't fit the bank's reality. Real scenarios:

- A QA engineer works on **two of three** banking apps but should not see the third
- A team manager configures the AI provider for the **whole team** but doesn't need to be a project member of every individual project
- A platform owner exists for installation/maintenance and is **not** day-to-day in any team's data

The three-layer model handles all three cases naturally:
- Project membership solves the "two of three apps" scope
- Team role gives the manager configuration powers without forcing them into every project
- Organization role lets the platform owner operate above any team

---

## 3. Multi-tenant data isolation

The platform is multi-tenant at the **organization** level. Within an organization, data is further isolated at the **project** level.

### 3.1 What's isolated by project membership
- Specifications, SpecificationSources, SpecChunks
- TestSuites, TestSections, TestScenarios, TestCases, TestCaseRevisions
- TestPlans, TestRuns, TestRunCases
- AutomationScripts, TestExecutions, TestResults, ExecutionSteps, TestArtifacts, ExecutionCheckpoints
- ExternalIssueLinks, IntegrationActionLogs (when project-scoped)

### 3.2 What's shared at team level
- TeamAIConfig + ModelProfiles (the team uses one AI configuration across all its projects)
- IntegrationConfig (the team's Jira / GitHub / Jenkins is shared by default; per-project overrides exist)
- ExecutionEnvironment definitions (browser/platform combos defined once at the team level)

### 3.3 What's enforced where
| Layer | Enforcement |
|---|---|
| ORM queryset scoping | `Project.objects.for_user(user)` — every list endpoint filters here |
| Object-level permissions | DRF permission classes on detail endpoints |
| WebSocket consumers | Stream tickets are execution-scoped and signed; can't subscribe across projects |
| Pre-signed MinIO URLs | Generated only for users with project access; URL TTL is short |

The principle: **the data layer enforces isolation; the view layer is just a convenience.** Even if a view leaked, the queryset wouldn't return another tenant's records.

---

## 4. Concurrency groups (per-project execution quotas)

This is the **gap relative to LambdaTest** that needs to be closed.

### 4.1 The problem
Browser capacity is shared. Even with separate `regression`, `interactive`, and `ai_agent` queues, one busy team or project can still consume the available Selenoid/Grid sessions unless admission control caps are enforced.

### 4.2 The LambdaTest pattern
LambdaTest organizes users into **Groups**. Each group has a max concurrent session cap. The org's total concurrency (e.g., 10 sessions) is divided among groups (e.g., 6 for Project A, 4 for Project B). One group can never starve another.

### 4.3 The BIAT solution
Add a `max_concurrent_executions` field on `Project`:

```python
class Project(models.Model):
    ...
    max_concurrent_executions = models.IntegerField(
        default=None,
        null=True,
        help_text="Max simultaneously running TestExecutions. None = no cap (uses full pool)."
    )
```

In `execution_runner.py`, before acquiring the run-case lease and starting an execution:

```python
if project.max_concurrent_executions is not None:
    running_count = TestExecution.objects.filter(
        run_case__run__project=project,
        status='running',
    ).count()
    if running_count >= project.max_concurrent_executions:
        # Defer — task stays queued, will retry shortly
        raise ProjectConcurrencyExceeded()
```

The Celery task on the queue retries with backoff. No new infrastructure. Just a counter and a cap.

### 4.4 The default
For now, `max_concurrent_executions=None` (no cap). When two projects start contending for capacity, the manager sets a per-project cap.

---

## 5. The workload queue model and tenancy

### 5.1 The queues are layer-driven, not tenant-driven
`regression`, `interactive`, and `ai_agent` are split by **workload**, not by project or team. All projects share those queues.

### 5.2 Why this is correct
A project's regression run and another project's regression run are doing the same kind of work — deterministic browser E2E scripts. Splitting them by tenant adds no value at this stage.

What matters is splitting **regression** from **interactive/debug** from **AI agent** so that long-running agent sessions cannot starve regressions, and bulk regressions cannot block a human waiting on a debug rerun.

### 5.3 Where tenancy intersects
Tenancy intersects with concurrency at the **per-project quota** level (section 4 above). The queue is shared; the slot inside the queue is gated per project.

---

## 6. The team workflow scenario

A concrete walkthrough. Setup:

```
Organization: BIAT
└── Team: QA Team (Manager: Rania)
    ├── TeamAIConfig (one AI provider, used by everyone)
    ├── IntegrationConfig (one Jira + one GitHub config)
    │
    ├── Project A — Banking App
    │   ├── Members: Ahmed, Sana, Youssef, Lina, Karim
    │   └── max_concurrent_executions = 2
    │
    └── Project B — Payments App
        ├── Members: Mariem, Nour, Tarek, Ines, Zied
        └── max_concurrent_executions = 1
```

### 6.1 Rania (Manager)
- `organization_role = member`, `TeamMembership(role='manager')`
- Sees both projects in dashboard
- Configures the AI provider once in `TeamAIConfig` — all 10 teammates benefit
- Sets up Jira and GitHub integrations once in `IntegrationConfig` — both projects use them
- Sets per-project concurrency caps
- Reads team-level reporting across both projects
- Does not interfere with anyone's day-to-day work

### 6.2 Ahmed (Project A member)
Logs in. His project list shows **only Project A** — Project B does not exist to him at the API level. Every query is scoped to his project memberships.

```
Morning:
  Ahmed opens Project A → Specifications tab
  Imports a Jira ticket from the banking app board
  AI agent reads the ticket → generates 3 candidate TestCases
  Ahmed reviews, approves all 3
  Three AutomationScripts are generated alongside (drafts)

Afternoon:
  Ahmed reviews the generated scripts, edits one, approves all
  Triggers a regression run on the 3 cases
  Goes through `regression` → 2 start (cap=2), 1 queues
  Ahmed clicks "Watch this run" → noVNC stream opens for one of them
  Run finishes → TestResults stored under Project A
```

### 6.3 Mariem (Project B member)
Identical experience to Ahmed but scoped entirely to Project B. Cannot:
- See Project A's test cases, runs, or results
- Subscribe to Ahmed's WebSocket stream (ticket is execution-scoped)
- Trigger anything that affects Project A's data

```
Same afternoon:
  Mariem launches a regression run on Project B
  cap=1 → her one run starts, the others queue
  Independent of Project A's contention
```

### 6.4 Two AI agent sessions running concurrently
```
10:00 — Ahmed triggers KaneAI session on Project A
  → `ai_agent` picks it up
  → Selenoid spins up Container #1
  → LangGraph drives Playwright in Container #1
  → noVNC stream auto-opens (always-on for agent)
  → Ahmed watches

10:02 — Mariem triggers KaneAI session on Project B
  → `ai_agent` picks it up (different worker)
  → Selenoid spins up Container #2
  → LangGraph drives Playwright in Container #2
  → noVNC stream auto-opens for Mariem
  → Mariem watches her own session

10:15 — Ahmed's session finishes
  → Container #1 destroyed
  → AutomationScript candidate created under Project A
  → Ahmed reviews

10:18 — Mariem's session finishes
  → Container #2 destroyed
  → AutomationScript candidate created under Project B
```

Zero data crossing. Zero stream visibility crossing. The only shared resource was the Celery worker dispatching the Docker run command.

---

## 7. Shared infrastructure, isolated data

```
SHARED (infrastructure layer):
├── Selenoid/Grid browser capacity (shared, gated by caps)
├── Celery queues (`regression`, `interactive`, `ai_agent`)
├── MinIO bucket (artifacts under project-scoped key prefixes)
├── Redis (Celery broker; channel groups are execution-scoped)
└── PostgreSQL (one DB; rows scoped by FK)

ISOLATED (data layer — enforced at queryset and serializer):
├── Specs, Cases, Plans, Runs, Executions, Results, Artifacts
├── ExternalIssueLinks, IntegrationActionLogs (when project-scoped)
└── WebSocket subscriptions (ticket-gated)
```

MinIO key examples:
```
artifacts/projects/<project_a_id>/executions/<exec_id>/screenshots/step_3.png
artifacts/projects/<project_b_id>/executions/<exec_id>/videos/full_run.mp4
```

When the frontend requests an artifact, the backend generates a pre-signed URL **only if** the user has access to that project. URL is short-lived (60–300s typical TTL).

---

## 8. AI access — the shared-key model

The whole team shares the AI configuration. Individual users never manage API keys. This matches LambdaTest's KaneAI license model.

### 8.1 The flow
```
Manager configures TeamAIConfig once:
  provider = "anthropic"
  model_profile[purpose=test_design].model = "claude-haiku-4-5"
  model_profile[purpose=test_design].api_key = encrypted("sk-ant-...")

Ahmed triggers AI test generation
  → Frontend POST /api/projects/<id>/ai/generate-tests/
  → Backend Celery task picks up
  → Worker reads TeamAIConfig → ModelProfile → decrypts API key
  → Worker calls Claude API
  → Response → candidate TestCases written under Project A

Mariem triggers AI session at the same time
  → Same flow, same key, completely independent call
  → Response → candidate TestCases written under Project B
```

Ahmed and Mariem never see the API key. They never configure anything. They just use AI features.

### 8.2 Why this is right
- One key = one billing line for the manager to monitor
- No risk of an individual user leaking their key
- New team members get AI access immediately on team join — no onboarding step
- Revoking a member doesn't require rotating keys

See [`07-ai-layer.md`](07-ai-layer.md) for the full AI configuration story including local Ollama deployment.

---

## 9. Special cases

### 9.1 Platform owner
- Has `organization_role = 'platform_owner'`
- Cannot be deleted via the API (backend rejects)
- Used for the bank's IT operations team — not for QA users
- Can create new organizations, change platform-wide settings

### 9.2 The view-only auditor
A team manager can add a user as `viewer` on a team to give read-only access across all the team's projects. Useful for compliance reviews.

### 9.3 Cross-project read for managers
Team managers see all projects in their team without being added to each. Implementation: queryset scoping checks `team_membership.role IN ('manager')` and includes the team's projects unconditionally.

### 9.4 Soft-delete
- Removing a project member sets `is_active=False` rather than hard-deleting (audit trail)
- Removing a team membership sets `is_active=False`
- Archiving a project sets `status='archived'` (still queryable, hidden from default lists)

---

## 10. What this gets us vs LambdaTest

| LambdaTest mechanism | BIAT equivalent | Status |
|---|---|---|
| Organization | `Organization` | Built |
| Sub-organization | — (not needed for one bank) | Skipped |
| Team | `Team` + `TeamMembership` | Built |
| Group (for concurrency) | `Project.max_concurrent_executions` | Designed, not yet built |
| User role (Admin / User / Guest) | `TeamMembership.role` | Built |
| Test visibility scoped to team | Project membership scoping | Built |
| KaneAI license allocation | `TeamAIConfig` + ModelProfile | Built (one config per team — implicitly all members get access) |
| API key shared by team | `TeamAIConfig` holds key, never user-facing | Built |
| Per-job concurrency in HyperExecute YAML | Per-project cap (simpler) | Designed, not yet built |

The biggest gap is **concurrency groups** (`max_concurrent_executions`). It's a one-field addition + one check in the runner. See [`roadmap.md`](../roadmap.md).
