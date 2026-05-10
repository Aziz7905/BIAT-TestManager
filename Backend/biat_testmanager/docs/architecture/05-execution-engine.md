# 05 — Execution Engine

**The execution queues. Selenium Grid/Selenoid. Language-specific Docker runner containers. The `__BIAT_EVENT__` protocol. Checkpoint resume. Manual browser sessions.**

---

## 1. The big picture

The execution engine is **two parallel pipelines** — one for Layer 2 browser E2E regression, one for Layer 3 AI browser authoring — backed by **three workload queues**: `regression`, `interactive`, and `ai_agent`. They share infrastructure but never share queue ownership.

```
┌────────────────────────────────────────────────────────────────────┐
│                     THE EXECUTION ENGINE                           │
│                                                                    │
│  ┌──────────────────────┐         ┌─────────────────────────┐      │
│  │  regression queue    │         │     ai_agent queue      │      │
│  │  (Layer 2)           │         │     (Layer 3)           │      │
│  │                      │         │                         │      │
│  │  Celery workers      │         │  Celery workers         │      │
│  │  -Q regression -c 4  │         │  -Q ai_agent -c 20      │      │
│  └──────────┬───────────┘         └────────────┬────────────┘      │
│             │                                  │                   │
│             ▼                                  ▼                   │
│  ┌──────────────────────┐         ┌─────────────────────────┐      │
│  │  Docker runner       │         │  LangGraph agent        │      │
│  │  containers          │         │  (in Celery worker)     │      │
│  │  (Selenium scripts)  │         │                         │      │
│  └──────────┬───────────┘         └────────────┬────────────┘      │
│             │                                  │                   │
│             ▼                                  ▼                   │
│  ┌──────────────────────┐         ┌─────────────────────────┐      │
│  │   Selenoid/Grid      │         │       Selenoid          │      │
│  │   Hub + Chrome nodes │         │  Disposable containers  │      │
│  └──────────────────────┘         └─────────────────────────┘      │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## 2. The three Celery queues

### 2.1 Why split, conceptually
- A regression run takes 30s–5min, deterministic, parallelizable across many cases
- An interactive/debug run is a single human-facing execution and should not wait behind a bulk regression
- An AI agent session takes 5–20 min, single-threaded, exploratory, can pause for LLM calls

If these share a queue and worker pool, one slow agent session can starve 30 regression tests, or one bulk regression can block a debug rerun while a human is waiting. That's unacceptable.

### 2.2 Configuration in `settings.py`

```python
CELERY_TASK_ROUTES = {
    "automation.run_test_execution": {"queue": "regression"},
    "automation.run_manual_browser_session": {"queue": "interactive"},
    "automation.expire_stale_execution_checkpoints": {"queue": "regression"},
    "automation.run_single_execution": {"queue": "interactive"},  # planned
    "automation.debug_rerun": {"queue": "interactive"},  # planned
    "ai.run_agent_session": {"queue": "ai_agent"},  # planned
}

CELERY_TASK_DEFAULT_QUEUE = "regression"
CELERY_TASK_QUEUES = (
    Queue("ai_agent", routing_key="ai_agent"),
    Queue("regression", routing_key="regression"),
    Queue("interactive", routing_key="interactive"),
)
```

### 2.3 Worker startup commands

```bash
# Regression worker pool — bulk browser E2E dispatch
celery -A biat_testmanager worker -Q regression --pool=prefork -c 4

# Interactive worker pool — manual sessions and debug reruns
celery -A biat_testmanager worker -Q interactive --pool=prefork -c 2

# Agent worker pool — I/O-bound LLM + browser sessions
celery -A biat_testmanager worker -Q ai_agent --pool=gevent -c 20

# Windows dev: use --pool=solo for each queue
```

Each worker locks itself to its queue with `-Q`. Capacity is independent.

### 2.4 Beat (scheduled tasks)
Beat runs separately. Currently:
```python
CELERY_BEAT_SCHEDULE = {
    "expire-stale-execution-checkpoints": {
        "task": "automation.expire_stale_execution_checkpoints",
        "schedule": 300.0,  # every 5 minutes
    },
}
```

Future agent-related schedules (e.g., periodic GitHub PR scans) will go here too.

---

## 3. Layer 2 — Regression execution path

### 3.1 Flow

```
1. User clicks "Run" on a TestRunCase (or a whole TestRun)
2. Backend calls create_execution_record(run_case)
   - Selects the active AutomationScript for the case
   - Resolves the ExecutionEnvironment (browser, platform)
   - Checks Project.max_concurrent_executions cap
   - If at cap: leaves task queued, will retry later
3. TestExecution row created with status='queued'
4. Celery task enqueued on `regression`
5. Worker picks up the task
6. Worker calls run_execution(execution_id)
7. acquire_run_case_lease() — claims the run-case
8. Status flips to 'running'
9. Worker spawns a Docker runner container (planned: replaces today's subprocess)
10. Runner container connects to the browser backend (Selenoid after Step 3; Selenium Grid today) via RemoteWebDriver
11. Script runs, emits __BIAT_EVENT__ events to stdout
12. Worker streams container logs, parses events
13. Each event creates/updates ExecutionStep, TestArtifact, ExecutionCheckpoint
14. WebSocket broadcasts events (only if stream_enabled=True)
15. Script exits → finalize_execution_result()
16. TestResult row written
17. TestRunCase.status synced from execution status
18. Run auto-closes if all run-cases are terminal
19. Lease released
20. Container destroyed (--rm)
```

### 3.2 Today vs. planned

| Step | Today | Planned (Step 3 in roadmap) |
|---|---|---|
| Script execution | Subprocess on Celery worker host | Docker runner container |
| Script dependencies | Whatever's installed on the worker | Per-language runner image, or script/team-owned custom image |
| Artifacts | Local filesystem under `artifact_dir/` | MinIO via boto3 |
| Worker→runner data | Direct disk access | Shared Docker volume + MinIO |
| Cleanup | Manual (and risky on crash) | Automatic via `--rm` |

### 3.3 Selenium Grid configuration
Currently `docker-compose.selenium-grid.yml` defines:
- **Hub** on `:4444` (and event bus on `:4442`/`:4443`)
- **3 Chrome nodes** (each: 1 session max, 1920×1080, 2GB shared memory)
- **noVNC ports**: `:7900`, `:7901`, `:7902` (one per node)

Scripts receive the hub URL via env var `BIAT_SELENIUM_GRID_URL` and use `selenium.webdriver.Remote(...)`.

### 3.4 Mapping `selenium_session_id` → noVNC URL
The `apps.automation.services.grid` module:
- Queries the Grid API for session info
- Maps a session id to its node's container
- Resolves the noVNC WebSocket URL (Docker port mapping or direct port)
- Caches results in Redis (4-hour TTL)
- Used for live streaming when `stream_enabled=True`

---

## 4. Layer 3 — AI agent execution path (planned)

### 4.1 Flow

```
1. User clicks "Start KaneAI session" on a TestCase or Jira ticket
2. Backend creates a TestExecution with trigger_type='agent'
   - Or a new dedicated AgentSession model — TBD during implementation
3. Celery task enqueued on `ai_agent`
4. Worker picks up the task
5. Worker initializes the LangGraph agent
   - Loads relevant SpecChunks via pgvector (RAG)
   - Loads existing TestCases for context
   - Loads the active TeamAIConfig + ModelProfile (for LLM provider)
6. Worker calls Selenoid API: POST /wd/hub/session
   - Selenoid spins up a fresh Chrome container
   - Returns a WebDriver session id
7. Agent starts executing:
   - LangGraph nodes call Playwright MCP tool to drive the browser
   - LangGraph nodes call LLM tool to plan / decide / generate
   - Each significant action emits a __BIAT_EVENT__-style event
8. WebSocket stream is ALWAYS open for agent sessions
   - User watches via noVNC (Selenoid's per-container VNC)
   - User sees the agent's narration in the step timeline
9. Agent finishes:
   - Writes candidate TestCase / AutomationScript records (status=draft / is_active=False)
   - Writes RCA / generated content as appropriate
10. Selenoid container destroyed automatically
11. Final session record persisted
```

### 4.2 Why Selenoid not Selenium Grid

| Concern | Selenium Grid | Selenoid |
|---|---|---|
| Container per session | No (persistent nodes) | Yes (fresh container) |
| State leakage between sessions | Possible | Impossible |
| Concurrency model | Bounded by node count | Bounded only by Docker capacity |
| Suitability for long sessions | Poor (a stuck session occupies a node) | Good (each session is its own container) |
| API surface | WebDriver protocol | WebDriver + extra control APIs |
| Recording | Possible but cluttered | First-class video recording per session |

For an AI agent that may explore for 15 minutes, leave artifacts in cookies, install extensions, or hit unexpected modals, Selenoid's per-session container is the right choice.

### 4.3 Selenoid container topology
```
┌──────────────────────────────────────┐
│         Selenoid (Aerokube)          │
│         API on :4444                 │
│                                      │
│  Spins up containers on demand:      │
│   ┌─────────────────────────────┐    │
│   │ aerokube/chrome:114.0       │    │
│   │ Session A — VNC :5900       │    │
│   └─────────────────────────────┘    │
│   ┌─────────────────────────────┐    │
│   │ aerokube/chrome:114.0       │    │
│   │ Session B — VNC :5901       │    │
│   └─────────────────────────────┘    │
└──────────────────────────────────────┘
```

Selenoid maps each session's VNC to a host port. The platform's noVNC consumer proxies WebSocket connections from the frontend to the right session's VNC port.

### 4.4 Future: Moon + Kubernetes
When the platform outgrows a single-host Selenoid (say, more than 5 concurrent agent sessions or more than 10 concurrent regressions), the path is:
- **Moon** — Aerokube's K8s-native multi-tenant grid (replaces Selenoid)
- **Kubernetes** — for general workload orchestration
- The `services/grid.py` and `services/selenoid.py` abstractions hide the difference; only the endpoint URLs change

This is **not in scope yet**. Current target: single-host Docker Compose with Selenoid.

---

## 5. Docker runner containers (the script execution environment)

### 5.1 The problem
Today, scripts run as subprocesses on the Celery worker host. Two problems:
1. **Dependency hell** — if a script needs Java/Maven tooling, Python packages, or a bank-owned dependency set that the worker doesn't have, it fails. Installing dependencies per script on the worker is slow and leaves zombie files.
2. **Filesystem coupling** — scripts write artifacts to the worker's local disk. When we move to containerized Selenium Grid (already done) or Selenoid, the filesystem isn't shared.

### 5.2 The solution: a runner container per execution

```
Celery worker
   ↓ uses Docker SDK (python `docker` library)
   ↓ docker run --rm
       --network biat-network
       -e BIAT_SELENIUM_GRID_URL=http://selenium-hub:4444
       -e BIAT_EXECUTION_ID=<id>
       -v <script-dir>:/app/script
       biat-selenium-java-runner:latest
       mvn test
   ↓ Streams container logs in real time
   ↓ Parses __BIAT_EVENT__ lines from stdout
   ↓ Persists ExecutionStep / TestArtifact rows
   ↓ Container exits → Docker removes it (--rm)
```

### 5.3 The pre-built runner images
Runner images are language-specific. The first-class bank target is Java Selenium; Python stays supported for prototypes and existing scripts.

```dockerfile
# Java E2E runner, simplified
FROM maven:3.9-eclipse-temurin-21
RUN mkdir -p /opt/biat
COPY biat-event-helper.jar /opt/biat/
```

```dockerfile
# Python E2E runner, simplified
FROM python:3.11-slim
RUN pip install selenium boto3 requests
COPY biat_event_helper.py /usr/local/lib/biat/
ENV PYTHONPATH=/usr/local/lib/biat
```

For most browser E2E scripts, one of these images is enough. The runner selected for an execution comes from `AutomationScript.language` first, then the execution environment default.

### 5.4 Custom dependencies
For scripts that need unusual libraries, `AutomationScript` can use optional fields:
- `requirements` — dependency list for the language-specific runner where supported
- `docker_image` — custom image override, usually a team-owned Java/Python image with bank-specific dependencies

If `docker_image` is set, the worker uses that image. If `requirements` is set, the runner installs the supported dependencies at start. If neither is set, the base runner for the script language is used.

### 5.5 Why skip per-script virtualenvs

| Approach | Verdict |
|---|---|
| Per-script virtualenv on worker host | **Reject.** Slow `pip install` on every run, zombie venv directories on crash, filesystem state leaks |
| Per-script Docker container | **Accept.** Clean isolation, automatic cleanup with `--rm`, no host state |

Going straight to containers skips a transitional layer that wouldn't have worked at scale.

### 5.6 Docker socket access
The Celery worker needs to talk to the Docker daemon to spin up runner containers. Two options:

| Option | Tradeoff |
|---|---|
| Mount `/var/run/docker.sock` into the worker container | Simple. Gives the worker container effective root on the host (acceptable risk for an internal bank platform) |
| Use Docker-in-Docker (`dind`) | More complex. More isolation. Worth it only at higher trust requirements |

Default: socket mount. Document the implication. If BIAT's security team requires `dind` later, switch.

---

## 6. The `__BIAT_EVENT__` protocol

Scripts running in the runner container emit structured events to stdout. The worker parses them in real time.

### 6.1 Wire format
```
__BIAT_EVENT__{"type":"step_started","step_index":3,"action":"click","selector":"#submit",...}
```

A line beginning with `__BIAT_EVENT__` followed by a JSON object. The worker reads container stdout line by line, splits on the prefix, parses the JSON.

### 6.2 Event types

| Event type | Purpose | Persists to |
|---|---|---|
| `step_started` | Step is beginning | `ExecutionStep` (insert) |
| `step_passed` | Step succeeded | `ExecutionStep` (update status, ended_at) |
| `step_failed` | Step failed | `ExecutionStep` (update with error) |
| `artifact_created` | Screenshot, video, or other file produced | `TestArtifact` (insert) |
| `require_human_action` | Pause for manual intervention | `ExecutionCheckpoint` (insert), worker waits |
| `agent_thought` (Layer 3) | Agent's reasoning | `ExecutionStep` (special type) |
| `agent_decision` (Layer 3) | Agent chose an action | `ExecutionStep` (special type) |

### 6.3 Helper API
Each supported runner language gets a tiny helper library that emits the same stdout protocol. Python uses `biat_event_helper.py`; Java should use an equivalent `biat-event-helper` package/JAR.

```python
from biat import (
    report_step_started,
    report_step_passed,
    report_step_failed,
    artifact_created,
    require_human_action,
)

report_step_started(index=1, action="login", selector="#submit-btn")
# ... do the action ...
report_step_passed(index=1)

artifact_created(path="/tmp/screenshot.png", artifact_type="screenshot", step_index=1)
```

The helper writes the JSON-encoded line to stdout with the `__BIAT_EVENT__` prefix. Authors don't deal with the wire format, and the worker parser stays language-agnostic.

### 6.4 Why this protocol
- **Language-agnostic** — anything that can write to stdout can emit events
- **Streamable** — events arrive in real time, not at the end
- **Robust** — non-event stdout (print debugging) is preserved as plain log lines
- **Testable** — the events can be captured and replayed for tests

---

## 7. Checkpoints (human-in-the-loop)

### 7.1 The flow
```
Script calls require_human_action(...) emitting a checkpoint event
       ↓
Worker creates ExecutionCheckpoint(status='pending')
       ↓
Worker writes a control file:
    <artifact_dir>/control/checkpoint-<key>.wait.json
       ↓
Script blocks waiting for the resume control file
       ↓
WebSocket broadcasts checkpoint_requested to the user
       ↓
User clicks "Resume" in the UI (or modifies state in the browser, then clicks Resume)
       ↓
Backend writes:
    <artifact_dir>/control/checkpoint-<key>.resume.json (with optional payload)
       ↓
Script wakes up, reads the resume payload, continues
       ↓
Worker updates ExecutionCheckpoint(status='resolved', resolved_by, resolved_at)
       ↓
WebSocket broadcasts checkpoint_resolved
```

### 7.2 The control file abstraction

Today: filesystem-based (`<artifact_dir>/control/...`)

Future (when runner is fully containerized): **Redis pub/sub** — the worker publishes to a key, the script in the container subscribes. This removes the shared-filesystem requirement.

```python
# Future
redis.publish(f"checkpoint:{execution_id}:{checkpoint_key}", json.dumps(payload))
```

### 7.3 Stop signal
`<artifact_dir>/control/execution.stop` (today, filesystem) or `redis.publish(f"execution:{id}:stop", "1")` (planned). Script polls for stop and exits cleanly.

### 7.4 Stale checkpoint expiry
Beat task `automation.expire_stale_execution_checkpoints` runs every 5 min, expires checkpoints older than 60 min that are still pending. The script in the container detects the timeout and aborts.

---

## 8. WebSocket streaming

### 8.1 Stream tickets
```
1. User opens execution detail page
2. Frontend POST /api/test-executions/<id>/stream-ticket/
3. Backend signs a short-lived ticket (TTL 120s) with payload {execution_id, user_id}
4. Frontend connects: ws/executions/<id>/?ticket=<ticket>
5. Consumer verifies ticket, checks user has project access, accepts
6. Consumer sends initial snapshot
7. Consumer publishes events as they happen via the channel layer
```

### 8.2 Events sent over the WebSocket
```
status_changed     — execution lifecycle transitions
step_event         — ExecutionStep insert/update
artifact_event     — TestArtifact insert
checkpoint_event   — ExecutionCheckpoint insert/update
result_event       — TestResult finalized
agent_event        — Layer 3 agent narration (planned)
```

### 8.3 Channel layer
- Production: Redis-backed channel layer
- Tests: in-memory channel layer (for deterministic Django test runs)

### 8.4 Stream policy (when to open)
See [`06-storage-and-streaming.md`](06-storage-and-streaming.md) for the full opt-in policy. Summary:
- Layer 3 agent sessions: **always** stream
- Debug rerun of a failed test: **always** stream
- "Watch this run" explicit click: stream
- Default regression run: **no** stream (silent execution)

---

## 9. The browser pixel stream (noVNC)

### 9.1 Architecture
```
Frontend (NoVncViewer component using the RFB library)
       ↓
WebSocket to backend Channels consumer
       ↓
Consumer proxies to the right backend:
   - Selenium Grid: ws://chrome-node:7900/...  (Layer 2)
   - Selenoid:      ws://selenoid-host:<dyn>/...  (Layer 3)
       ↓
Browser pixels stream back to frontend
```

### 9.2 Why a backend proxy
The frontend can't connect directly to the Grid node (firewall, internal network). The backend consumer is on the same network as the Grid/Selenoid and proxies the WebSocket. This also lets us enforce auth on the stream — the user's JWT and project access are checked before the proxy is established.

### 9.3 Stream URLs
- `ws/executions/<id>/browser/` — the noVNC pixel stream for an execution (auth + session id resolution)
- `ws/executions/<id>/?ticket=<>` — the event stream (status, steps, artifacts)

These are two independent WebSocket connections. The frontend can open one or both depending on context.

---

## 10. Manual browser sessions

### 10.1 Use case
A QA engineer wants to open a browser **without running a test** — just to inspect the app, check a fix, demonstrate something. The "Open browser" button on a test case starts a manual browser session.

### 10.2 Implementation
- A `TestExecution` is created with `trigger_type='diagnostic'`
- No `AutomationScript` is attached
- A worker (on `interactive`) connects to the browser backend, opens a fresh Chrome session, navigates to the target URL
- The session stays alive until the user closes it or a TTL expires
- The user interacts with the browser via the noVNC stream (mouse and keyboard work — RFB is bidirectional)

### 10.3 Service
`apps.automation.services.manual_browser` — `start_manual_browser_session()` and `close_manual_browser_session()`. Same `__BIAT_EVENT__` infrastructure for telemetry.

---

## 11. Engine abstraction (for future engines)

`apps.automation.services.engine` defines a contract: each engine (Selenium, Playwright) has a `run(script, environment, callbacks)` method. The runner picks the engine based on `AutomationScript.framework` first, falling back to `ExecutionEnvironment.engine`.

Today, both engines flow through `python_script_runner.py` which spawns the script as a subprocess. After the runner-container migration, both flow through the Docker SDK with their respective base images.

This abstraction is **why** Layer 3's Playwright MCP usage doesn't pollute Layer 2 — Layer 3 talks to a different engine adapter that connects to Selenoid via Playwright's CDP-over-WebDriver, not via the standard Selenium client.

---

## 12. Summary: what each layer's execution looks like

| Concern | Layer 2 (regression) | Layer 3 (AI agent) |
|---|---|---|
| Queue | `regression` for bulk runs, `interactive` for debug/manual | `ai_agent` |
| Browser farm | Selenoid after Step 3 (Selenium Grid today) | Selenoid (disposable containers) |
| Driver protocol | Selenium WebDriver | Playwright MCP → CDP |
| Script source | Stored `AutomationScript` content | Generated by LangGraph at runtime |
| Live stream | Opt-in (default off) | Always on |
| Artifacts | MinIO under project key prefix | MinIO under project key prefix |
| Cleanup | `--rm` runner container | Selenoid auto-destroys session container |
| Concurrency cap | Per-project `max_concurrent_executions` | Per-project (same field) |
| Failure mode | Step fails → execution fails | Agent decides recovery / escalation |
