# Roadmap

**The build order. What is done, what is next, in what sequence and why.**

**Last updated:** 2026-05-08

---

## How to read this document

Each step is a **distinct, ship-able unit of work** with:
- Why it's next (the problem it solves)
- What changes (concrete, scoped)
- Why this order (what it unblocks, what it depends on)
- Definition of done

Steps are sequenced. Don't skip ahead — earlier steps are foundations for later ones.

---

## Where we are

### Layer 1 — Test management — **complete and stable**
- Tenancy + RBAC: Organization, Team, TeamMembership, Project, ProjectMember, UserProfile
- Specs: full ingestion pipeline (sources, records, specifications, chunks with pgvector)
- Repository: Suite → Section → Scenario → Case → Revision (revision-safe)
- Planning: Plans, Runs, RunCases — including `run_kind` field (planned/standalone/system_generated)
- Reporting: project overview, pass-rate trends, failure hotspots
- Integrations foundation: IntegrationConfig, RepositoryBinding, WebhookEvent, ExternalIssueLink, IntegrationActionLog with HMAC-signed webhook ingestion

### Layer 2 — Regression execution — **mostly complete, gaps**
- Celery + Selenium Grid integration ✓
- WebSocket execution streaming ✓
- Checkpoint pause/resume ✓
- `__BIAT_EVENT__` runtime helper protocol ✓
- `selenium_session_id` field for noVNC URL mapping ✓
- Manual browser sessions ✓

**Gaps:**
- Single Celery queue (no `ai_agent` / `regression` / `interactive` separation)
- Subprocess execution on worker host (no Docker runner containers)
- Local filesystem artifacts (no MinIO)
- Filesystem control signals (should move to Redis pub/sub for containerized runners)
- No per-team capacity caps
- Stream is on by default (should be opt-in for regression/interactive, always-on for ai_agent)
- No "debug rerun" mode
- No Results Ingest API for the hybrid path (external CI / IDE → platform)
- Selenium Grid is the only browser backend; Selenoid migration is pending

### Schema cleanup — **pending**
- `Team` still holds AI provider/key/model fields that should live only in `TeamAIConfig`
- `Team` still holds Jira/GitHub/Jenkins integration fields that should live only in `IntegrationConfig`
- `UserProfile` still holds `jira_token` / `github_token` that should live only in `UserIntegrationCredential`
- No `IntegrationResolverService` exists yet

### Layer 3 — AI agent — **not started**
- `TeamAIConfig`, `ModelProfile`, `AIProvider` models exist ✓
- Zero LLM calls in the codebase
- No LangGraph
- No Playwright MCP
- No Selenoid running
- No `AIAgentSession` model
- No `BrowserSessionManager` abstraction

---

## The build order

```
Step 1  →  Three Celery queues (ai_agent / regression / interactive)
Step 2  →  Schema consolidation + IntegrationResolverService
Step 3  →  Selenoid + Docker runner + MinIO + stream policy
            (also: BrowserSessionManager abstraction, drop Selenium Grid)
Step 4  →  Per-team capacity caps + debug rerun + AIAgentSession model + LLM provider abstraction
Step 5  →  Phase E — LangGraph live agent (THE GOAL: KaneAI core loop)
Step 6  →  Results Ingest API (hybrid path: external CI / IDE → platform)
Step 7  →  Phase D — AI offline generation (RCA, then test/script generation)
Step 8  →  GitHub source-of-truth sync
Step 9  →  GitHub PR validation + Jira ticket → test generation
Step 10 →  Phase F — Self-healing
Step 11 →  Scale: Moon + Kubernetes (only when needed)
```

The agent layer is reached after **5 steps**. Steps 6–9 enrich the platform around the agent and are reorderable.

---

## Step 1 — Three Celery queues

### Why now
Foundational. Every later step assumes workload isolation. AI agent sessions cannot share a worker pool with regression bursts or single-test executions.

### What changes
**`settings.py`:**
```python
from kombu import Queue

CELERY_TASK_DEFAULT_QUEUE = "regression"
CELERY_TASK_QUEUES = (
    Queue("ai_agent", routing_key="ai_agent"),
    Queue("regression", routing_key="regression"),
    Queue("interactive", routing_key="interactive"),
)
CELERY_TASK_ROUTES = {
    "automation.run_test_execution": {"queue": "regression"},
    "automation.run_manual_browser_session": {"queue": "interactive"},
    "automation.expire_stale_execution_checkpoints": {"queue": "regression"},
    # Future tasks (not yet implemented):
    # "ai.run_agent_session": {"queue": "ai_agent"},
    # "ai.generate_failure_rca": {"queue": "ai_agent"},
    # "ai.generate_tests_from_spec": {"queue": "ai_agent"},
    # "automation.run_single_execution": {"queue": "interactive"},
    # "automation.debug_rerun": {"queue": "interactive"},
}
```

**Worker startup:**
```bash
# Linux production
celery -A biat_testmanager worker -Q ai_agent    --pool=gevent  -c 20
celery -A biat_testmanager worker -Q regression  --pool=prefork -c 4
celery -A biat_testmanager worker -Q interactive --pool=prefork -c 2

# Windows dev
celery -A biat_testmanager worker -Q ai_agent    --pool=solo
celery -A biat_testmanager worker -Q regression  --pool=solo
celery -A biat_testmanager worker -Q interactive --pool=solo
```

The `ai_agent` queue uses **gevent** because agent loops are I/O-bound (LLM calls + browser actions). One worker process serves 20 concurrent sessions.
The `regression` and `interactive` queues use **prefork** because they spawn subprocess runners (CPU-bound coordination).

### Definition of done
- Settings declare three queues with routing rules
- All current tasks are routed to the right queue
- Worker startup documentation updated in `README.md`
- A small test asserts each task lands on its expected queue

### What it does not do
Doesn't add the agent task. Doesn't change runner behavior. Just routing.

---

## Step 2 — Schema consolidation + IntegrationResolverService

### Why now
Before the AI layer or any agent code, the data model needs **one source of truth per concern**. The agent will call resolvers, never read fields directly. If `Team.ai_provider` and `TeamAIConfig.provider` both exist, the resolver picks between two sources and drift starts.

This is cheap (1–2 days), no production data to migrate, and unblocks Steps 4 and 5.

### What changes

**Remove from `Team` (already in `TeamAIConfig`):**
- `ai_provider`, `ai_api_key`, `ai_model`, `monthly_token_budget`, `tokens_used_this_month`

**Remove from `Team` (move to `IntegrationConfig`):**
- `jira_base_url`, `jira_project_key`, `github_org`, `github_repo`, `jenkins_url`

**Remove from `UserProfile` (move to `UserIntegrationCredential`):**
- `jira_token`, `github_token`

**Keep on `UserProfile` (these are identity, not credentials):**
- `slack_user_id`, `teams_user_id`, `notification_provider`, `notifications_enabled`

**New service:** `apps/integrations/services/resolver.py`
```python
def resolve_integration_credentials(
    *, provider: str, team: Team, project: Project | None,
    actor_user: User | None, mode: Literal["act_as_user", "act_as_app"],
) -> IntegrationCredentialBundle:
    """
    mode="act_as_app"  → returns IntegrationConfig credentials (the platform's bot token)
    mode="act_as_user" → returns UserIntegrationCredential for actor_user; falls back
                         to act_as_app only if explicitly allowed by IntegrationConfig
    """
```

**Compatibility:** API serializers that previously exposed `team.ai_provider` etc. now read through `team.ai_config.provider.slug`. Frontend types adjust accordingly.

### Definition of done
- Migration removes the deprecated fields from `Team` and `UserProfile`
- All read sites use `TeamAIConfig` / `IntegrationConfig` / `UserIntegrationCredential`
- `IntegrationResolverService` exists with at least Jira and GitHub coverage
- Existing tests pass; new tests cover the resolver's `act_as_user` vs `act_as_app` paths

### What it does not do
Doesn't change any API contracts that don't reference the removed fields. Doesn't touch execution behavior.

---

## Step 3 — Selenoid + Docker runner + MinIO + stream policy

### Why now
The biggest single piece of work. Four changes are coupled because they all hinge on the move from "execution lives on the worker host" to "execution lives in containers":
1. Selenoid replaces Selenium Grid as the single browser backend (one container per execution, isolated, VNC built-in)
2. Docker runner containers replace subprocess execution (solves dependency hell)
3. MinIO replaces local-filesystem artifacts (solves bloat, enables horizontal workers)
4. Stream policy: opt-in for regression/interactive, always-on for ai_agent

**`BrowserSessionManager`** abstraction is introduced here so Step 11 (Moon + K8s) is a config change, not a refactor.

### What changes

**Infrastructure:**
- `docker-compose.yml` — adds Selenoid (`aerokube/selenoid`), MinIO (`minio/minio`)
- Selenoid config (`browsers.json`) for Chrome image versions
- MinIO bucket initialization (`biat-artifacts`)
- All containers on a shared Docker network so the runner can reach Selenoid + MinIO
- Selenium Grid Hub + nodes are removed from `docker-compose.yml`

**Runner image (`Dockerfile.runner`):**
- Base Python 3.11-slim + selenium + boto3 + biat_event_helper
- Image built and loaded into the worker's Docker daemon
- Optional `docker_image` field on `AutomationScript` lets a script pin a custom image

**`BrowserSessionManager` Protocol** in `apps/automation/services/browser_sessions.py`:
```python
class BrowserSessionBackend(Protocol):
    def allocate(self, *, session_id, browser, capabilities) -> BrowserSessionHandle: ...
    def release(self, handle: BrowserSessionHandle) -> None: ...
    def health_check(self, handle: BrowserSessionHandle) -> bool: ...

class SelenoidBackend(BrowserSessionBackend): ...   # active
class MoonBackend(BrowserSessionBackend): ...       # Step 11 only
```

All runner code talks to the Protocol — never imports Selenoid directly.

**`apps/automation/services/python_script_runner.py`:**
- Replace `subprocess.Popen(...)` with `docker.run(...)`
- Stream container logs in real time (Docker SDK)
- Pass execution_id, MinIO credentials, BrowserSessionManager-resolved WebDriver URL via env vars
- Container destroyed automatically with `--rm`

**`apps/automation/services/storage.py` (new):**
- `boto3` wrapper for MinIO
- `upload_artifact(execution_id, file_path, artifact_type)` → returns storage_key
- `get_presigned_url(storage_key, ttl_seconds)` → returns URL

**`TestArtifact` model migration:**
- Add `storage_backend` (default `'minio'`), `storage_key` (CharField)
- Keep `file_path` as nullable for transition; backfill existing rows

**`TestExecution` model migration:**
- Add `stream_enabled` (BooleanField, default `False`)
- Add `debug_rerun` (BooleanField, default `False`)

**Streaming policy:**
- WebSocket consumer for noVNC stream checks `execution.stream_enabled` before accepting
- AI agent sessions auto-set `stream_enabled=True`
- Manual browser sessions auto-set `stream_enabled=True`
- Default regression / interactive executions get `stream_enabled=False` unless flagged for debug rerun or "Watch this run"

**Control signals (filesystem → Redis pub/sub):**
- `apps/automation/services/control.py` rewritten to use Redis
- Stop / checkpoint resume signals broadcast via Redis channels
- Runner script subscribes (replaces filesystem polling)

### Definition of done
- A regression run completes end-to-end in a Docker runner container connected to Selenoid
- Artifacts upload to MinIO, downloadable via pre-signed URL
- A run with `stream_enabled=False` cannot open a noVNC stream
- A run with `stream_enabled=True` can open a noVNC stream
- Selenoid spins a container per session, session id maps to a noVNC URL
- All existing tests pass; new tests for storage adapter, runner container, stream gating
- Selenium Grid `docker-compose` file removed

### What it does not do
- Doesn't ship the AI agent
- Doesn't ship debug rerun UX (Step 4)
- Doesn't change Layer 1 anything

---

## Step 4 — Per-team caps + debug rerun + AIAgentSession + LLM abstraction

### Why now
The last set of foundations before Step 5 (LangGraph). Each piece is small but each is required:
- **Per-team capacity caps** prevent one team from monopolizing the Selenoid `LIMIT`
- **Debug rerun** is the live-stream regression escape hatch
- **`AIAgentSession`** is the persisted state that lets agent sessions survive worker restarts
- **LLM provider abstraction** is what the agent will call instead of importing OpenAI directly

### What changes

**`TeamCapacityLimit` model:**
```python
class TeamCapacityLimit(models.Model):
    team = models.OneToOneField(Team, on_delete=models.CASCADE)
    max_concurrent_ai_sessions = models.IntegerField(default=5)
    max_concurrent_regression_runs = models.IntegerField(default=10)
```

Service-level admission check before queuing any execution. If the team is at cap, the API returns 429 with a clear message; the request never enters the queue.

**Debug rerun endpoint:**
- `POST /api/test-executions/<id>/debug-rerun/`
- Creates a new `TestExecution` from the same `(test_case, script, environment)` with `trigger_type='manual'`, `debug_rerun=True`, `stream_enabled=True`
- Routed to the `interactive` queue
- Frontend opens noVNC stream automatically when navigating to a debug rerun

**`AIAgentSession` model:**
```python
class AIAgentSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    test_case = models.ForeignKey(TestCase, null=True, on_delete=models.SET_NULL)

    status = models.CharField(...)  # queued, provisioning, active, paused, completed, failed, expired
    backend = models.CharField(...)  # "selenoid" | "moon"
    backend_handle = models.JSONField(default=dict)  # vnc_url, webdriver_url, container_id

    agent_state = models.JSONField(default=dict)         # LangGraph state snapshot
    recorded_actions = models.JSONField(default=list)    # for script generation
    pending_amendments = models.JSONField(default=list)  # Phase 3 amendment loop

    last_activity_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True)
    ended_at = models.DateTimeField(null=True)
```

A Celery beat task kills sessions idle > 60 min.

**LLM provider abstraction in `apps/ai/providers/`:**
```python
class LLMProvider(Protocol):
    def chat(self, messages: list[dict], **opts) -> str: ...
    def chat_json(self, messages: list[dict], schema: dict) -> dict: ...

class OpenAIProvider(LLMProvider): ...
class AzureOpenAIProvider(LLMProvider): ...   # production target for BIAT
class AnthropicProvider(LLMProvider): ...
class OllamaProvider(LLMProvider): ...        # local on-prem
class GroqProvider(LLMProvider): ...          # cheap dev

def get_llm_provider(team: Team) -> LLMProvider:
    """Reads TeamAIConfig → returns the configured provider."""
```

Agent code calls `get_llm_provider(team).chat(...)` — never imports a provider SDK directly.

### Definition of done
- A team capped at 3 cannot start a 4th AI session (returns 429, never queued)
- "Debug Rerun" button on a failed execution creates a streamed `interactive`-queue execution
- `AIAgentSession` rows can be created, updated, and queried
- LLM provider abstraction has at least two working implementations (one cloud, one local)
- A beat task expires stale agent sessions

### What it does not do
- Doesn't yet run a real agent loop (that's Step 5)
- Doesn't add the `Project.max_concurrent_executions` cap (deferred unless needed)

---

## Step 5 — Phase E — LangGraph live agent (the goal)

### Why now
All upstream pieces are in place: queues split, Selenoid running, MinIO storing artifacts, `AIAgentSession` model, LLM abstraction. This is the headline feature of the product — the KaneAI-equivalent core loop.

### What changes

**`apps/ai/agent/graph.py`** — LangGraph state graph with three explicit phases:

**Phase 1 — Generation (offline, no browser)**
- Input: prompt + spec doc (optional) + URL + optional screenshot/context
- If a spec doc is attached: parse → chunk → embed (BAAI/bge-m3, local) → store as `SpecChunk` rows
- LLM retrieves relevant chunks via similarity search, generates a `GenerationDraft` (Suite/Section/Scenario/Cases with steps + preconditions + test data)
- User reviews/edits/approves at each level (HUMAN GATE)
- Approved drafts become real `TestSuite` / `TestSection` / `TestScenario` / `TestCase` rows

**Phase 2 — Live authoring (per case, looped)**
- `BrowserSessionManager.allocate(...)` spawns a Selenoid container with the requested config
- Frontend opens noVNC viewer pointing at the VNC URL — user watches live
- For each step in the case:
  - LLM + Playwright MCP determine next browser action
  - Execute via Playwright MCP, take screenshot, append to action history
  - On selector failure: vision LLM + DOM accessibility tree → corrected selector (one retry); else HUMAN GATE
- DOMInspector runs in parallel: looks for missing scenarios (e.g. "Forgot password" link), collects `AmendmentProposal` rows
- After the last step: serialize action history into a Selenium Python script

**Phase 3 — Refine & save**
- Amendment proposals fed back to the LLM with the original `GenerationDraft` → updated draft
- User reviews diff, accepts/rejects new scenarios (HUMAN GATE)
- Accepted amendments loop back to Phase 2 to author the new cases
- Generated Selenium scripts saved as `AutomationScript` rows on each test case
- `TestCaseRevision` created when authoring updated existing case content
- Screenshots + recorded actions persisted to MinIO via the storage service

**MCP tools used by the agent:**
- Playwright MCP — browser actions
- DOMInspector MCP — DOM analysis for amendments
- SelfHealing MCP — vision + DOM-driven selector repair
- SpecRetrieval MCP — pgvector similarity over `SpecChunk`
- RepositoryService MCP — Suite/Section/Scenario/Case CRUD
- AutomationScriptService MCP — save scripts
- ArtifactService MCP — MinIO uploads

**WebSocket extensions:**
- New event types: `agent_thought`, `agent_decision`, `agent_action_attempted`, `agent_action_result`, `amendment_proposed`
- Two separate WebSocket consumers per session:
  - `/ws/ai-sessions/{id}/browser/` — RFB pass-through to Selenoid VNC port
  - `/ws/ai-sessions/{id}/agent/` — JSON event stream of agent reasoning

**Memory model:**
- **Short-term** (per session): `AIAgentSession.agent_state` JSONB. Survives worker restarts.
- **Long-term** (cross-session): `SpecChunk` pgvector + existing repository / scripts / results queried directly via services.

### Definition of done
- A user can submit a prompt + spec + URL → review the generated plan → watch the agent author each case live → end with `AutomationScript` rows attached to each `TestCase`
- The session is fully isolated in its own Selenoid container
- Per-team capacity caps are enforced
- Multiple users can run concurrent sessions without interference
- All tool calls + agent decisions logged
- Token usage tracked per session

### What it does not do
- Doesn't validate the generated script by running it (the optional Validation Agent is a polish item to add inline if needed)
- Doesn't push scripts to GitHub (Step 8)
- Doesn't file Jira tickets (Step 9)
- Doesn't self-heal during regression playback (Step 10)

---

## Step 6 — Results Ingest API (hybrid path)

### Why now
With the agent shipping, the platform's TestRail-equivalent surface is ready to accept results from external execution paths. This closes the hybrid model: tests can run on the platform OR on the engineer's laptop / Jenkins / GitHub Actions, both feeding the same `TestExecution` rows.

### What changes

**New endpoint:**
- `POST /api/test-run-cases/{id}/ingest-result/`
- Accepts JUnit XML or a structured JSON payload
- Creates a `TestExecution` (`trigger_type='external'`) + `TestResult` + `ExecutionStep` rows + `TestArtifact` for any uploaded screenshots/logs
- Updates `TestRunCase.status` from the result

**Authentication:** the endpoint accepts a per-team API token (separate from JWT), stored on `IntegrationConfig` for CI use. Engineers use their own JWT.

**Reporting** automatically includes externally-ingested results — no special handling, the data model is uniform.

### Definition of done
- A POSTed JUnit XML produces visible results in the platform with no manual work
- A user can mix in-platform and external runs in the same `TestPlan` / `TestRun`
- API is documented in `README.md`

### What it does not do
- Doesn't push results back out
- Doesn't trigger external CI from inside the platform

---

## Step 7 — Phase D — AI offline generation (RCA + offline test/script)

### Why now
With the agent (Step 5) shipping, the LLM client and prompt machinery exist. Offline AI features become small wins on top of the same plumbing.

### What changes

**`apps/ai/services/generation.py`:**
- `generate_failure_rca(execution)` — reads execution + steps + screenshots + DOM → calls LLM → updates `TestResult.ai_failure_analysis`. Triggered automatically on failed regression runs when the team has AI configured.
- `generate_tests_from_spec(specification)` — RAG-retrieves chunks, generates `TestCase` candidates with `design_status='draft'`. Reviewed in the UI before promotion.
- `generate_script_from_case(test_case)` — generates an `AutomationScript` candidate (`is_active=False`) for an approved test case.

**WebSocket event** `rca_ready` so live UIs update without polling.

### Definition of done
- A regression failure produces an RCA visible in the UI
- A spec → tests workflow produces draft `TestCase` rows in a review queue
- Token budget tracking works
- MLflow logs every LLM call

---

## Step 8 — GitHub source-of-truth sync

### Why now
With the agent and offline generation shipping, engineers want a clean way to author scripts in their IDE and keep them synced. Independent of AI, but pairs naturally with the agent (the agent can also push generated scripts to GitHub).

### What changes

**`AutomationScript` model:**
```python
source_repo_binding = models.ForeignKey(RepositoryBinding, null=True, on_delete=models.SET_NULL)
source_repo_path = models.CharField(max_length=500, blank=True)
pinned_commit_sha = models.CharField(max_length=40, blank=True)
last_synced_at = models.DateTimeField(null=True, blank=True)
```

**`apps/integrations/services/github_sync.py`:**
- Webhook consumer for `push` events → matches changed files to `AutomationScript.source_repo_path` → updates `script_content` + `pinned_commit_sha`
- Manual sync endpoint: `POST /api/automation-scripts/<id>/pull-from-github/`

**UI:** when `source_repo_binding` is set, the script editor is read-only; "Pull from GitHub" replaces "Save".

### Definition of done
- Push to a bound repo updates the corresponding `AutomationScript` automatically
- Next regression run uses the new content
- `IntegrationActionLog` shows the sync event

---

## Step 9 — GitHub PR validation + Jira ticket → test generation

### Why now
Combines Steps 5, 7, 8. Closes the developer-loop: PR opens → agent picks tests → runs them → posts results back to the PR. Mirrors KaneAI's GitHub flow.

### What changes

**GitHub PR validation:**
- Webhook consumer reacts to `pull_request.opened`, `pull_request.synchronize`, `issue_comment` (trigger `@biat validate this PR`)
- Service reads PR diff → RAG-searches affected tests → selects existing or generates new ones → triggers regression run + (if needed) agent session
- Posts a markdown comment to the PR with results + RCA + video URLs

**Jira ticket → test generation:**
- "Generate from Jira ticket" UI action
- Service reads the issue, retrieves linked specs, generates `TestCase` candidates as drafts
- Creates `ExternalIssueLink` records

**Reverse direction — bug filing:**
- "Create Jira bug" button on a failed `TestExecution`
- Composes summary + description + RCA + attachments (presigned MinIO URLs)
- Posts via Jira API
- Creates `ExternalIssueLink`

All external operations go through `IntegrationResolverService` (Step 2).

### Definition of done
- `@biat validate this PR` works end-to-end on a real PR
- Jira ticket → candidate tests works end-to-end
- Failure → Jira bug works end-to-end

---

## Step 10 — Phase F — Self-healing

### Why now
Last major AI feature. Needs Steps 4 (LLM provider) + 5 (agent infrastructure). Spec is in `backlog.md`.

### What changes

See [`backlog.md`](backlog.md) for the full spec. Summary:
- Restore `HealingEvent` model with the upgraded shape (status PENDING, candidate_selectors JSON, reviewed_by, applied_to_revision)
- Detection: runner catches `NoSuchElementException` → emits `healing_triggered`
- Generation: LangGraph node proposes candidate selectors with confidence
- Application: auto-approve if confidence > threshold, else escalate via `ExecutionCheckpoint`
- Audit: `HealingEvent` records the full trail

---

## Step 11 — Scale: Moon + Kubernetes

### Why this is last
Migrate when:
- Sustained 15+ concurrent agent sessions on Selenoid
- Sustained 20+ concurrent regressions
- Single-host Docker capacity is exhausted

At that point, swap:
- Selenoid → **Moon** (Aerokube's K8s-native multi-tenant grid, free + paid tiers)
- Celery workers → K8s pods with HPA on queue depth
- The `BrowserSessionManager` Protocol (Step 3) hides the difference; only endpoint URLs change

This is **deliberately not on the near-term roadmap.** It's documented so the path exists.

---

## What's NOT on the roadmap (and why)

| Feature | Why deferred |
|---|---|
| Cross-browser testing (Firefox, Safari, Edge) | Banking apps work on Chrome; expand later |
| Real device testing (iOS, Android) | Out of scope for MVP; needs cloud device farm or real devices |
| Visual regression / Smart UI | Different problem class; not a KaneAI core feature |
| Performance / load testing | Different problem class |
| API testing as runtime | Spec ingestion handles documentation; API runtime testing is its own engine |
| Playwright runtime for regression | Selenium is the firm's engine; Playwright stays in Layer 3 only |
| Sub-organizations | Single bank, not needed |
| Per-user AI keys | KaneAI doesn't do this either; team-level is correct |
| Agent-learning memory (per-user / per-project preferences) | Research-grade, deferred until after the core loop is stable |
| Multi-framework code export (Java, JavaScript) | Marketing surface; Selenium Python covers BIAT's needs |

These are not "future phases" — they're decisions to not pursue them within the current product vision.

---

## How to keep this document current

- When a step is finished, update its section: change "What changes" to past tense, mark "Definition of done" complete
- Don't delete completed steps — leave them as historical record
- When a new step is needed mid-stream, insert it in the right place (don't re-number; use 4.5 if needed)
- Keep step descriptions self-contained — someone reading this in 6 months should understand what happened
