# 07 — AI Layer

**`TeamAIConfig`. API key management. Ollama deployment. Phase D (offline generation). Phase E (live agent — KaneAI equivalent). Phase F (self-healing). AI RCA.**

---

## 1. The AI configuration model (already built, not yet called)

### 1.1 What's wired
The data model for AI is fully in place. **No code anywhere makes an LLM call yet** — but the configuration plumbing is done.

```
Team
  └── TeamAIConfig (one per team)
       ├── monthly_token_budget
       ├── tokens_used_this_month
       └── ModelProfile (one per purpose)
            ├── purpose: test_design | review | execution
            ├── deployment_mode: local | cloud | hybrid
            ├── endpoint_url
            ├── api_key (encrypted)
            ├── model_name
            └── provider → AIProvider (reference data)
```

### 1.2 The purpose-based split
A team has multiple `ModelProfile` rows — one per purpose. This lets the team route different work to different models:

| Purpose | Typical model | Why |
|---|---|---|
| `test_design` | Small fast model (Claude Haiku, llama3-8B local) | Generates many small candidates from a Jira ticket; cost-sensitive |
| `review` | Same as test_design or slightly larger | Validates the generated candidates against the spec |
| `execution` | Large reasoning model (Claude Opus, GPT-4) | Drives the LangGraph agent during a live session — needs strong reasoning |

A team can use a free local model for `test_design` and a paid cloud model for `execution`, or any other combination. The platform doesn't dictate.

### 1.3 The `AIProvider` reference table
Static reference data: known providers (Anthropic, OpenAI, Mistral, Ollama, Groq, etc.) with default endpoints. New providers can be added without code changes — just a new row.

---

## 2. API keys: server-side, never user-facing

### 2.1 The rule
**The team's manager configures the AI key once. Individual users never see it, never configure it, never need their own.**

This matches LambdaTest's KaneAI license model: org admin allocates licenses, users get access without managing keys.

### 2.2 The flow

```
Manager (Rania) configures TeamAIConfig:
  endpoint_url = "https://api.anthropic.com"
  api_key = "sk-ant-..."   (encrypted at rest with FIELD_ENCRYPTION_KEY)
  model_name = "claude-opus-4-7"

Ahmed (member, Project A) clicks "Generate tests from this Jira ticket"
       ↓
Frontend POST /api/projects/<id>/ai/generate-tests/  body: {ticket_id: ...}
       ↓
Django view authorizes (Ahmed has project access)
       ↓
Celery task enqueued on agent_queue (or a dedicated ai_queue if separated later)
       ↓
Worker runs:
  1. Read TeamAIConfig for Ahmed's team
  2. Decrypt the api_key
  3. Build the LLM client (Anthropic SDK with the key)
  4. Read SpecChunks via pgvector (RAG context)
  5. Read existing TestCases for context
  6. Call the LLM
  7. Parse response → candidate TestCases
  8. Write TestCase rows with design_status='draft'
       ↓
Frontend polls / WebSocket: candidates appear in Ahmed's review queue

Ahmed never sees the API key. Mariem (Project B) running concurrent AI work makes
independent calls with the same key. Both calls are server-side.
```

### 2.3 Why this is right
- **One key = one billing line.** The manager monitors `tokens_used_this_month` against `monthly_token_budget`. They don't need to chase individual users.
- **Onboarding is automatic.** A new team member gets AI access the moment they join. No "request a key" step.
- **Revocation is simple.** Remove the team membership → user loses AI access immediately. No key rotation required.
- **Compliance.** API keys never appear in browser localStorage, never in network logs from the client side, never in user-visible UI.

### 2.4 Encryption at rest
`ModelProfile.api_key` uses `django-encrypted-model-fields` with `FIELD_ENCRYPTION_KEY` from settings. The DB stores ciphertext. Decrypt happens only in the Celery worker, not in the view layer.

---

## 3. Ollama and local models

### 3.1 Why local models matter for a bank
- **Data sovereignty** — the LLM call sees the spec content, the test cases, possibly Jira ticket content. For sensitive specs, this content should not leave the network.
- **No marginal cost per call** — useful for high-volume operations like spec re-indexing or generating many test candidates
- **No internet dependency** — works offline, doesn't fail when the bank's outbound is throttled

### 3.2 The deployment question
"If the manager runs Ollama on their personal machine, how do other team members access it?"

**Key insight: the LLM call is made from the Celery worker (server-side), never from the user's browser.** What matters is whether the Celery worker can reach the Ollama HTTP endpoint.

### 3.3 Three deployment options

#### Option A — Ollama on the server (the right answer)
```
Server (running Django + Celery + Redis + ...) also runs Ollama
  ollama serve   # listens on localhost:11434

TeamAIConfig:
  endpoint_url = "http://localhost:11434"

Worker → calls localhost → Ollama responds
All teammates get AI access via the server
```

This is the right setup. The server is always on. No network hops. Everyone benefits.

#### Option B — Ollama on the manager's personal PC (works but fragile)
```
Manager's PC: OLLAMA_HOST=0.0.0.0:11434 ollama serve

TeamAIConfig:
  endpoint_url = "http://192.168.1.45:11434"   # manager's LAN IP

Worker (on server) → calls manager's PC over LAN → Ollama responds
```

Works but: manager turns off PC → AI features go down for everyone. Latency is higher. Not recommended unless temporary.

#### Option C — Ollama on a dedicated GPU machine (future, when models grow)
```
Dedicated GPU box: OLLAMA_HOST=0.0.0.0:11434 ollama serve

TeamAIConfig:
  endpoint_url = "http://gpu-server.bank.local:11434"

Worker → reaches GPU box over the bank's network → fast inference
```

Best for production-scale use of large models like `llama3:70b` that need GPU acceleration.

### 3.4 Mixing local and cloud per purpose
The `ModelProfile` per purpose makes mix-and-match natural:
```
ModelProfile(purpose=test_design, deployment_mode=local,  endpoint=localhost:11434, model=llama3:8b)
ModelProfile(purpose=review,      deployment_mode=local,  endpoint=localhost:11434, model=llama3:8b)
ModelProfile(purpose=execution,   deployment_mode=cloud,  endpoint=api.anthropic.com, model=claude-opus-4-7)
```

Cheap operations stay local. Heavy reasoning goes to the cloud model. The team's AI bill is bounded.

---

## 4. The three AI phases (D, E, F)

The AI work is sequenced into three phases. They build on each other.

### 4.1 Phase D — Offline AI test generation

**What it is:** the user gives the platform a spec or a Jira ticket; the platform generates candidate test cases.

**No browser, no live agent, no real-time interaction.** Pure LLM call, asynchronous, output appears in a review queue.

**Flow:**
```
1. User opens a Specification in the platform
2. User clicks "Generate tests from this spec"
3. Backend Celery task on agent_queue:
   a. Retrieves the spec's chunks (RAG context)
   b. Retrieves nearby existing TestCases (avoid duplication)
   c. Builds a prompt: "given this spec, generate 5 test cases in this JSON schema..."
   d. Calls LLM via TeamAIConfig
   e. Parses the JSON response
   f. Validates each candidate against the TestCase schema
   g. Creates TestCase rows with design_status='draft', generated_by='ai_offline'
4. Frontend: candidates appear in the user's review queue
5. User reviews each candidate:
   - Edit fields if needed
   - Approve → design_status='approved', candidate becomes canonical
   - Reject → soft-delete with reason
```

**The same Phase D applies to scripts:**
```
1. User opens an approved TestCase
2. User clicks "Generate automation script"
3. Backend Celery task:
   a. Reads the TestCase's structured steps
   b. Reads any existing AutomationScript for similar cases (style precedent)
   c. Calls LLM with the prompt: "write a Selenium Python script that..."
   d. Validates: parse the script, run script_validation
   e. Creates AutomationScript row with is_active=False, generated_by='ai_offline'
4. User reviews the script in the editor
5. User clicks "Activate" → is_active=True (and deactivates other active scripts for the same case)
```

**What's in scope for Phase D:**
- LLM client wrappers (Anthropic, OpenAI, Ollama)
- Prompt templates for each generation type
- JSON schema validation of LLM output
- Token budget tracking
- Review queue UI (covered in frontend docs)
- Generation telemetry (logged to MLflow)

**What's NOT in Phase D:**
- Live agent (that's Phase E)
- Self-healing (that's Phase F)
- RCA (could be Phase D minor or Phase E early)

### 4.2 Phase E — Live AI agent (the KaneAI equivalent)

**What it is:** the user starts an "agent session." A LangGraph agent drives a Playwright browser in a Selenoid container, exploring the app to either record actions, validate behavior, or generate tests live.

**Browser is real, live, watchable. The user sees the agent's reasoning narrated in the UI. The user can pause, intervene, or take over.**

**Architecture:**
```
LangGraph agent (orchestrator)
  ├── Tool: Playwright MCP (browser control via MCP protocol)
  ├── Tool: SpecChunk RAG (semantic search over specs)
  ├── Tool: TestRepository search (find similar tests)
  ├── Tool: Jira API (read tickets, post comments)
  ├── Tool: GitHub API (read PR diffs, post comments)
  └── Tool: AutomationScript writer (output → candidate)

Graph nodes:
  Plan → Execute → Observe → Decide → Generate → Verify → Submit
```

**Two main use cases:**

#### Use case 1 — Author a test from a Jira ticket
```
User selects a Jira ticket → "Generate tests with agent"
       ↓
Agent (in Selenoid container):
  1. Reads ticket via Jira API
  2. RAG-retrieves the relevant spec chunks
  3. Plans the test scenarios needed
  4. Opens the bank's app in the browser
  5. For each scenario: drives the app, records the steps
  6. Translates recorded actions → Selenium Python script
  7. Writes candidate TestCase + AutomationScript
       ↓
User watches via noVNC stream
User reviews candidates
```

#### Use case 2 — Validate a GitHub PR
```
GitHub webhook fires on PR open or update
       ↓
Agent:
  1. Reads PR diff via GitHub API
  2. Identifies which app components changed
  3. RAG-retrieves existing tests covering those components
  4. Selects relevant tests OR generates new tests for new behavior
  5. Triggers regression run on selected tests
  6. Waits for results
  7. Generates RCA if any failed
  8. Posts a comment on the PR with results + RCA
```

**What's in scope for Phase E:**
- LangGraph agent with the toolset above
- Playwright MCP integration
- Selenoid integration (separate doc — see [`05-execution-engine.md`](05-execution-engine.md))
- Live noVNC stream for agent sessions (always on)
- Agent narration → step events on the WebSocket
- Candidate output flow (same review queue as Phase D)

**What's NOT in Phase E:**
- Self-healing (that's Phase F)

### 4.3 Phase F — Self-healing

**What it is:** during a regression run, when a Selenium step fails because a selector broke, the agent proposes new selectors and either auto-applies (high confidence) or escalates to a human checkpoint.

**See [`backlog.md`](../backlog.md) for the full self-healing spec — it was deliberately removed in Phase 6.5 and is documented for return.**

**Quick summary:**
```
Regression script runs → step_failed event with selector + DOM snapshot
       ↓
Backend detects: this is a selector failure (not a logic failure)
       ↓
Agent kicks in:
  1. Receives the failed selector + DOM snapshot
  2. Proposes 1-3 candidate selectors with confidence scores
  3. If best candidate confidence > threshold → auto-apply, resume execution
  4. Else → create ExecutionCheckpoint, pause, notify human reviewer
  5. Human approves or rejects via the checkpoint UI
       ↓
Approved fix is written back to:
  - The AutomationScript (if confidence is high)
  - OR a per-case selector override store (if we want to keep the canonical script clean)
       ↓
HealingEvent record persists the audit trail
```

**Why this is its own phase:**
- It needs Phase D (the LLM provider must work) and Phase E (the agent infrastructure must work)
- It changes regression flow — needs to be done after the regression flow is stable
- The model design is non-trivial — see [`backlog.md`](../backlog.md)

---

## 5. AI RCA (Root Cause Analysis) — earliest AI win

The smallest useful AI feature. Should ship first inside Phase D.

### 5.1 The flow
```
Test fails (any failure)
       ↓
finalize_execution_result() runs as today
       ↓
NEW: ai_rca_for_failure() async task triggered if AI is configured
       ↓
Celery task reads:
  - TestExecution.error_message + stack_trace
  - All ExecutionStep rows (especially the failed one)
  - The failure screenshot artifact
  - The DOM snapshot artifact (if present)
  - Recent commits to the linked GitHub repo (if integration is configured)
       ↓
Builds an LLM prompt with all the context
       ↓
LLM responds with human-readable explanation:
  "The login button selector #submit no longer matches the rendered DOM.
   In commit a3f4b2 (3 hours ago), the markup changed to use class .btn-primary.
   Recommended fix: update the script's selector. Alternative: enable
   self-healing (Phase F) to auto-update broken selectors."
       ↓
TestResult.ai_failure_analysis = LLM response
       ↓
Frontend shows the RCA on the failure detail page
```

### 5.2 Why it's the right first AI feature
- All inputs already exist (steps, screenshots, error message)
- Pure read operation on existing data — no risk of corrupting models
- Immediate user value — a human-readable explanation of every failure
- Can run on cheap models (Claude Haiku, GPT-4o-mini) — minimal cost
- Frontend just renders text — no complex new UI
- Tests the AI plumbing end-to-end (TeamAIConfig → ModelProfile → LLM client → response → DB)

### 5.3 Why it goes inside Phase D
RCA is a generation task — given context, produce text. It uses the same `ModelProfile.purpose='test_design'` (or a new `purpose='analysis'`) plumbing as test generation. No browser, no LangGraph, no agent. Pure Phase D.

---

## 6. RAG: how AI sees the platform's data

The AI never operates blind. It always has context retrieved from the platform's own data.

### 6.1 Spec retrieval (already built)
```
Query: a Jira ticket description (or natural language prompt)
       ↓
Embed the query with BAAI/bge-m3 (1024-dim)
       ↓
pgvector cosine similarity search over SpecChunk.embedding
       ↓
Top-k chunks (typical k=5-15) returned with their content
       ↓
Inject into LLM prompt as RAG context
```

### 6.2 Test repository retrieval (planned)
Similar but on a separate index — find existing tests that cover similar functionality, to:
- Avoid generating duplicates
- Inform style and naming conventions
- Detect when an existing test should be updated rather than a new one written

### 6.3 Code retrieval (planned, Phase E for GitHub integration)
When the agent analyzes a PR:
- Fetch the diff
- Fetch the surrounding context (function definitions, etc.)
- Optionally embed and search for related test code

This stays planned — no code yet.

---

## 7. Token budgets and observability

### 7.1 The budget mechanic
`TeamAIConfig` has:
- `monthly_token_budget` — the cap (in tokens)
- `tokens_used_this_month` — running counter, reset on the 1st

Before an LLM call, the worker checks: are we under budget? If yes, proceed. If no, refuse and log the refusal. The user sees a clear error: "AI budget exhausted for this month — contact your manager."

### 7.2 MLflow telemetry
Every LLM call logs to MLflow:
- Model used, prompt length, response length
- Token counts (input + output)
- Latency
- Purpose tag (test_design / review / execution / rca)
- Project tag
- User tag

This gives the manager a dashboard of: "where is our AI spend going? Which projects use the most? Which model purpose is most expensive?"

### 7.3 Embedding telemetry
Embedding runs (re-indexing specs) also log to MLflow. Different experiment from generation but same backbone.

---

## 8. Prompt engineering practices

### 8.1 Prompts live in code, not the database
Every prompt is defined in a Python module under `apps/<app>/prompts/`. They're version-controlled, code-reviewed, and tested. **No prompt-injection from user input** — all user input is treated as data, never templated raw into instructions.

### 8.2 Prompt caching (when using Claude)
For long contexts (a big spec, the test repository), Claude's prompt caching reduces cost massively. The static parts of a prompt (system instructions, RAG context that's the same across many calls in a session) are marked for caching. This is a Phase E optimization once the agent is making many calls per session.

### 8.3 Output as JSON, validated
All generation prompts ask for JSON output matching a known schema. The response is parsed; validation failure → retry with a clarification prompt; second failure → fall back to a simpler prompt.

---

## 9. The data the AI is allowed to see

This matters for compliance. The AI sees:
- Specifications (intentional — they're the input)
- Test cases (intentional — they're the output)
- Automation scripts (intentional — same)
- Execution failure context (RCA inputs)
- Jira ticket content (when generating from a ticket)
- GitHub PR diffs (when validating a PR)

The AI does **not** see:
- User personal data (emails, passwords)
- Other teams' data (multi-tenant isolation enforced before AI calls)
- Production banking data (test data is anonymized; if it isn't, the team is misusing the platform)

The decision of whether to use a cloud model or a local model can be made per-purpose based on what the prompt would contain. Local models are recommended for sensitive specs.

---

## 10. Where the AI code will live

| Concern | Path (planned) |
|---|---|
| LLM client adapters (Anthropic, OpenAI, Ollama) | `apps/ai/clients/` |
| Prompt templates | `apps/ai/prompts/` |
| Generation services (test gen, script gen, RCA) | `apps/ai/services/generation.py` |
| LangGraph agent (Phase E) | `apps/ai/agent/graph.py` |
| Playwright MCP wrapper | `apps/ai/agent/tools/browser.py` |
| Tools (Jira, GitHub, RAG) | `apps/ai/agent/tools/` |
| Celery tasks for AI | `apps/ai/tasks.py` |

A new `ai` app houses all of this. It depends on `accounts` (for `TeamAIConfig`), `specs` (for RAG), `testing` (for repository), `automation` (for scripts and execution), and `integrations` (for Jira/GitHub).

This separation matters: turning AI off means disabling one app, not unwinding logic spread across the others.
