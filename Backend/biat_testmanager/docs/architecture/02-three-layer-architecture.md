# 02 — Three-Layer Architecture

**The full walkthrough of the three layers, what each one actually does, what flows between them, and why the separation matters.**

---

## 1. The principle: three independent layers, stacked

The platform is built as three layers. Each layer is independently useful — you can turn off the layers above it and the platform still works.

```
            ┌─────────────────────────────────────────┐
            │   LAYER 3: AI AGENT (KaneAI equivalent) │
            │       depends on Layer 2 + Layer 1      │
            └─────────────────────────────────────────┘
                              ↓
            ┌─────────────────────────────────────────┐
            │   LAYER 2: REGRESSION EXECUTION         │
            │       depends on Layer 1                │
            └─────────────────────────────────────────┘
                              ↓
            ┌─────────────────────────────────────────┐
            │   LAYER 1: TEST MANAGEMENT              │
            │       independent — useful alone        │
            └─────────────────────────────────────────┘
```

This is not just diagramming. It's a **build constraint**. If you cannot turn off Layer 3 and have a working Layer 2, the layers have leaked into each other and we've built a monolith.

---

## 2. Layer 1 — Test Management

### 2.1 Purpose
Pure data organization. The TestRail equivalent. Manages requirements, test cases, plans, runs, and results without doing any execution.

### 2.2 Core entities
- **Specifications** (`Specification`, `SpecificationSource`, `SpecificationSourceRecord`, `SpecChunk`) — what the bank's apps are *supposed* to do
- **Repository** (`TestSuite` → `TestSection` → `TestScenario` → `TestCase` → `TestCaseRevision`) — what the QA team *tests*
- **Planning** (`TestPlan` → `TestRun` → `TestRunCase`) — what the QA team is *running this week*
- **Results** (`TestResult` — created by Layer 2, but stored at Layer 1)
- **Reporting** — pass-rate trends, failure hotspots, dashboard overview
- **Integrations** (`IntegrationConfig`, `RepositoryBinding`, `WebhookEvent`, `ExternalIssueLink`) — Jira/GitHub/Jenkins linkage

### 2.3 What Layer 1 explicitly does NOT do
- Does not run any browser
- Does not spawn any subprocess
- Does not call any AI provider
- Does not stream over WebSocket (the streaming subsystem belongs to Layer 2)

### 2.4 What it produces
The output of Layer 1 is a **clean, queryable, versioned dataset** of everything the QA team knows about its requirements, tests, and historical runs. This dataset is what Layer 2 consumes (to know what to run) and what Layer 3 consumes (as RAG context for AI generation).

### 2.5 Manual test execution lives here
A QA tester reading a test case and marking it manually pass/fail in the UI is a Layer 1 operation. No browser. No script. Just a `TestRunCase.status` update with a comment. This is the TestRail-style "manual run" workflow.

---

## 3. Layer 2 — Regression Execution

### 3.1 Purpose
Run **deterministic Selenium browser E2E scripts** against a Docker browser pool, capture results, write artifacts. The HyperExecute equivalent at small scale, scoped to browser automation.

### 3.2 Core flow
```
Layer 1 says: "execute test case X under plan Y"
         ↓
TestExecution created (status=queued)
         ↓
Celery task enqueued on `regression`
         ↓
Worker picks up task → spawns Docker runner container
         ↓
Runner container connects to Selenoid → drives a Chrome browser
         ↓
Script runs, emits __BIAT_EVENT__ events to stdout
         ↓
Worker streams logs, parses events, persists ExecutionStep / TestArtifact
         ↓
Final TestResult written, TestRunCase.status synced back
         ↓
WebSocket consumers (if any are subscribed) get notified
         ↓
Layer 2 has done its job — Layer 1 has fresh result data
```

### 3.3 Sources of scripts
A script in `AutomationScript` can come from any of three places:
1. **Engineer wrote it in the platform editor** — typical for small teams or when engineers don't have a strong IDE workflow
2. **Engineer wrote it in their IDE and pushed to GitHub** — the platform syncs the script content via webhook (see [`08-integrations.md`](08-integrations.md))
3. **AI agent generated it** — Layer 3 produced a candidate, a human reviewed and approved it, it became canonical

Layer 2 does not care about the origin. It runs whatever's in `AutomationScript.script_content`.

### 3.4 The three workload queues — why
The execution layer has **three Celery queues**, not one:

- `regression` — bulk saved-script browser E2E execution
- `interactive` — single executions, debug reruns, and manual browser sessions
- `ai_agent` — long-lived LangGraph/Playwright MCP browser authoring sessions

Why split? Because an AI agent session can take 5–15 minutes, a regression burst can contain many cases, and an interactive debug run has a human waiting. If they share a queue and worker pool, one workload can starve the others.

Workers are started with `-Q regression`, `-Q interactive`, or `-Q ai_agent` to lock them to their workload. Capacity is independent.

### 3.5 What Layer 2 explicitly does NOT do
- Does not generate scripts
- Does not analyze failures with AI
- Does not propose selector fixes
- Does not drive browsers via Playwright (Selenium only — Playwright belongs to Layer 3 via MCP)

### 3.6 Live streaming — opt-in, not always-on
Nobody watches 1000 regression tests run live. The default for Layer 2 executions is **silent execution** — results captured, video recorded as an artifact, no live noVNC stream opened.

Three exceptions trigger a live stream:
1. The user explicitly clicked "Watch this run" before triggering it
2. The user is doing a **debug rerun** — clicking on a failed test and rerunning it specifically to see what went wrong
3. The execution is part of a Layer 3 agent session (handled by Layer 3, not Layer 2)

See [`06-storage-and-streaming.md`](06-storage-and-streaming.md) for the full streaming policy.

---

## 4. Layer 3 — AI Agent

### 4.1 Purpose
The KaneAI equivalent. An AI agent that uses Layer 1 (RAG context, repository data) and Layer 2 (the same browser farm and result-recording infrastructure) to do five things:

1. Generate test cases from Jira tickets
2. Generate or select tests from GitHub PR diffs
3. Drive a browser live to record actions in natural language
4. Self-heal broken selectors during regression runs
5. Generate human-readable RCA for failures

### 4.2 Architecture
```
LangGraph agent (the orchestrator)
  ├─ Tool: Playwright MCP (browser control)
  ├─ Tool: Jira API (read tickets, create bugs)
  ├─ Tool: GitHub API (read PR diffs, post comments)
  ├─ Tool: SpecChunk RAG (retrieve relevant specs from pgvector)
  ├─ Tool: TestRepository RAG (retrieve relevant existing tests)
  └─ Tool: AutomationScript writer (output → AutomationScript candidate)
```

The agent runs as a Celery task on `ai_agent`. The LangGraph graph defines the steps the agent goes through (analyze, plan, execute, observe, decide). The graph nodes can call tools. Tools are explicit — no surprise external calls.

### 4.3 The browser
Layer 2 and Layer 3 both use **Selenoid** as the browser backend. Regression runs use it silently by default; AI/manual/debug sessions enable the noVNC stream because a human is expected to watch.

Selenoid spins up a Docker container for each browser session and destroys it when done. This is exactly what an AI agent needs: a clean, disposable environment per session, with no risk of leaking state from a previous session into a new one.

### 4.4 Live streaming — always on
Every Layer 3 session has a live noVNC stream. The user **needs** to watch the agent work — that's the product experience. The whole point of an AI agent driving a browser is that you can see what it's doing in real time and intervene if needed.

### 4.5 Output: candidates, not commits
Layer 3 never writes directly to canonical models. Everything it produces is a **candidate**:

- AI-generated test case → `TestCase` with `design_status=draft`
- AI-generated script → `AutomationScript` with `is_active=False`
- AI-generated bug analysis → posted to a review queue, not auto-committed to Jira

A human reviews. Approves or rejects. Only on approval does the candidate become canonical. This rule is not negotiable — the bank's QA processes require human sign-off on every test asset.

### 4.6 What Layer 3 explicitly does NOT do
- Does not run regression suites at scale (that's Layer 2)
- Does not bypass the canonical models
- Does not auto-commit anything without human approval
- Does not own a separate browser farm; it uses the same Selenoid backend through Layer 2 seams
- Does not store its own data — it reads from Layer 1, writes candidates back to Layer 1

---

## 5. What flows between the layers

```
┌────────────────┐                                          ┌────────────────┐
│                │  reads spec chunks via pgvector (RAG)    │                │
│                │ ←─────────────────────────────────────── │                │
│                │                                          │                │
│   LAYER 1      │  reads existing test cases               │   LAYER 3      │
│   (data)       │ ←─────────────────────────────────────── │   (AI agent)   │
│                │                                          │                │
│                │  writes candidate TestCase, candidate    │                │
│                │  AutomationScript (status=draft)         │                │
│                │ ←─────────────────────────────────────── │                │
│                │                                          │                │
│                │  triggers Layer 2 execution              │                │
│                │ ←─────────────────────────────────────── │                │
│                │                                          │                │
└────────────────┘                                          └────────────────┘
        ▲                          ▲
        │                          │
        │   reads what to run      │   writes results, steps, artifacts
        │                          │
        │                          │
┌────────────────┐
│                │
│   LAYER 2      │
│   (execution)  │
│                │
└────────────────┘
```

### 5.1 Layer 1 → Layer 2
"Run this `TestRunCase`." That's the only thing Layer 1 says to Layer 2. Layer 1 doesn't dictate how. Layer 2 figures out which `AutomationScript` to use, which environment, etc.

### 5.2 Layer 2 → Layer 1
"Here are the results." Layer 2 writes `TestResult`, `ExecutionStep`, `TestArtifact` rows back into Layer 1's data store. Then Layer 2's job is done.

### 5.3 Layer 1 → Layer 3
"Here is the spec / the existing test / the Jira ticket." Layer 3 is a heavy reader of Layer 1. RAG retrievals, repository lookups, integration config reads.

### 5.4 Layer 3 → Layer 1
"Here is a candidate test case / candidate script / candidate bug analysis." Layer 3 writes drafts back to Layer 1. A human reviews. On approval, the draft becomes canonical.

### 5.5 Layer 3 → Layer 2
"Run this script I just wrote." Layer 3 can trigger Layer 2 executions. The execution runs through Layer 2's normal `regression` or `interactive` pipeline — Layer 2 doesn't know it was an AI agent that asked.

### 5.6 Layer 2 → Layer 3
Nothing direct. Layer 2 doesn't know Layer 3 exists. Layer 3 *observes* Layer 2 results by reading Layer 1's data store.

This unidirectionality matters. Layer 2 must remain ignorant of AI. If you find yourself writing `if self.is_ai_session:` inside a Layer 2 service, the layer separation is bleeding.

---

## 6. The shared infrastructure

These pieces are used by multiple layers but conceptually belong to the platform, not to any one layer:

| Infrastructure | Used by | Purpose |
|---|---|---|
| **PostgreSQL + pgvector** | Layer 1 (canonical data), Layer 3 (RAG embeddings) | Data store |
| **Redis** | Layer 2 (Celery broker, channel layer, control signals), Layer 3 (Celery broker) | Task queue + pub/sub |
| **MinIO** | Layer 2 (artifacts), Layer 3 (recorded videos) | Object storage |
| **Django Channels / Daphne** | Layer 2 (execution streams), Layer 3 (agent live view) | WebSocket transport |
| **Celery workers** | Layer 2 (`regression`, `interactive`), Layer 3 (`ai_agent`) | Task runners (separate worker pools) |

When we say "shared," we mean it physically. Logically, each layer's use of these resources is namespaced (separate queues, separate Redis keys, separate MinIO bucket prefixes, separate channel groups).

---

## 7. The "if turned off" test

The cleanest way to verify the layer separation is the *if turned off* test:

| Question | Answer |
|---|---|
| If you delete Layer 3 entirely, does Layer 2 still run regression tests? | **Yes** — Layer 2 doesn't import Layer 3 anywhere |
| If you delete Layer 2 entirely, does Layer 1 still let you manage cases and plan runs? | **Yes** — Layer 1 doesn't depend on execution |
| If you delete Layer 1, does Layer 2 work? | **No** — Layer 2 has no data to run against |
| If you delete Layer 1, does Layer 3 work? | **No** — Layer 3 has nothing to write candidates into |

This dependency direction is the architecture in one sentence: **Layer 1 stands alone; Layer 2 needs Layer 1; Layer 3 needs both.**

---

## 8. Why this matters in practice

### 8.1 Hiring and ownership
Different engineers can own different layers. A backend engineer who knows Django and PostgreSQL can fully own Layer 1 without touching Selenium or LLM APIs. A DevOps-ish engineer can own Layer 2's Docker / Selenoid concerns. An AI engineer can own Layer 3's LangGraph and prompt engineering. The layer split makes specialization possible.

### 8.2 Incremental shipping
Layer 1 was shipped first. Layer 2 was shipped on top. Layer 3 will ship last. Each layer became useful before the next one started. We never had a "nothing works until everything works" moment.

### 8.3 Replaceability
If we ever want to replace a layer (e.g., swap LangGraph for AutoGen in Layer 3, or replace Selenoid with Moon in Layer 2), the change is contained. The other two layers don't notice.

### 8.4 Testing
Each layer can be tested in isolation. Layer 1 is just Django ORM tests. Layer 2 can be tested with a fake script runner. Layer 3 can be tested with a recorded LangGraph trace and mocked tools.

---

## 9. The diagram one more time, with paths

```
              [Manager/Tester UI]
                    │
                    ▼
          ┌─────────────────────┐
          │     LAYER 1         │
          │  (Django REST API)  │
          └─────────┬───────────┘
                    │
        ┌───────────┼─────────────┐
        ▼                         ▼
  ┌───────────┐            ┌──────────────┐
  │  LAYER 2  │            │   LAYER 3    │
  │ (Celery + │            │ (Celery +    │
  │  Selenoid │            │  LangGraph + │
  │           │            │  Selenoid)   │
  └─────┬─────┘            └──────┬───────┘
        │                         │
        ▼                         ▼
 [Selenoid]                 [Selenoid]
 [Chrome browser]           [Browser containers]
        │                         │
        └────────┬────────────────┘
                 ▼
           [MinIO bucket]
        (artifacts, videos)
```

Three workload queues, one near-term browser backend direction (Selenoid), one shared object store, one shared database, one Django app. That's the whole shape.
