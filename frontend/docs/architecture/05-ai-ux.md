# 05 — AI UX (Phase D + E)

**AI test generation UI. Review queues. Agent live view. RCA viewer. The KaneAI experience, on the frontend.**

---

## 1. The AI surfaces overview

The AI features map onto frontend surfaces:

| Backend phase | Backend feature | Frontend surface |
|---|---|---|
| Phase D | RCA on failures | RCA panel inside Automation tab result view |
| Phase D | AI test generation from spec | Generate button on Specifications tab + review queue |
| Phase D | AI script generation from case | Generate button in Test Case editor + review |
| Phase E | Live agent (KaneAI authoring) | "Author with agent" launcher + live agent view |
| Phase E | GitHub PR validation | Triggered by webhook, results posted to PR (no in-app UI besides logs) |
| Phase E | Jira ticket → tests | "Generate from Jira" button + review queue |
| Phase F | Self-healing | Healing review queue (when confidence is below auto-threshold) |

All AI surfaces live inside the project workspace as a new **AI tab** plus inline affordances on existing tabs.

The UX should stay honest about scope: the KaneAI-like experience is for browser E2E authoring first. Other test categories can be represented in planning, traceability, and ingested results, but the UI should not present performance/security/API/unit/integration execution as first-party BIAT automation until backend engines exist.

---

## 2. RCA panel (the smallest, ships first)

When `TestResult.ai_failure_analysis` is populated:

```
┌──────────────────────────────────────────────────────┐
│  RESULT: FAILED ✗                                    │
│  Step 4 failed: NoSuchElementException               │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │  AI Root Cause Analysis                      │   │
│  │  ─────────────────────────────────           │   │
│  │  The login button selector "#submit" no       │   │
│  │  longer matches the rendered DOM. In commit   │   │
│  │  a3f4b2 (3 hours ago), the markup changed     │   │
│  │  to use class ".btn-primary".                 │   │
│  │                                              │   │
│  │  Recommended fix: update the script's        │   │
│  │  selector. Alternative: enable self-healing.  │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  [View failed script] [Create Jira bug]              │
└──────────────────────────────────────────────────────┘
```

**Implementation:**
- Pure read component — renders `result.ai_failure_analysis` as markdown
- Uses a markdown library (TBD when shipping — likely `react-markdown`)
- "Create Jira bug" → opens a confirmation modal, then calls the bug-creation endpoint
- If RCA hasn't been generated yet (still processing): show a "Analyzing failure..." spinner with WebSocket subscription to `rca_ready` event

---

## 3. The review queue (Phase D)

A central place to review AI-generated candidates before they become canonical.

### 3.1 Layout
```
┌──────────────────────────────────────────────────────┐
│  AI REVIEW QUEUE                                     │
│                                                      │
│  Filter: [All] [Test Cases] [Scripts] [Failed Imports]│
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │ TestCase candidate                             │ │
│  │ "User can recover password via email"          │ │
│  │ Generated from: Jira PROJ-456                 │ │
│  │ Status: Draft (4 candidates from this ticket) │ │
│  │                            [Review] [Reject]  │ │
│  └────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────┐ │
│  │ AutomationScript candidate                     │ │
│  │ For TestCase #234 "User can login"             │ │
│  │ Generated from: case structure                │ │
│  │ Status: Draft                                  │ │
│  │                            [Review] [Reject]  │ │
│  └────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

### 3.2 The Review modal
Clicking "Review" opens a modal showing:
- The AI-generated content (case fields filled in, or script in a code editor)
- An "Edit" mode that lets the user modify before approval
- A "Source" panel showing what the AI read (Jira ticket excerpt, retrieved spec chunks)
- Actions: **Approve as-is**, **Approve with edits**, **Reject** (with reason)

### 3.3 The diff view (for script candidates)
When AI generates an `AutomationScript` to *update* an existing case (e.g., the case was edited and the script needs regeneration), show a diff:

```
┌──────────────────────────────────────────────────────┐
│  Script update for TestCase #234                     │
│  ────────────────────────────────────────────────    │
│  - driver.find_element(By.ID, "submit").click()     │
│  + driver.find_element(By.CSS, ".btn-primary").click()│
│                                                      │
│       [Approve update] [Reject] [Edit before approve]│
└──────────────────────────────────────────────────────┘
```

---

## 4. Generation triggers — where they live

### 4.1 From a Specification (Phase D)
On the Specifications tab, each imported `Specification` gets a **"Generate tests"** button:

```
Specification: "Account Recovery Flow v2.3"
Indexed: ✓ (47 chunks)

[Generate tests from this spec]
```

Clicking opens a wizard:
1. *"How many test candidates would you like? (1–10, default 5)"*
2. *"Focus area? (optional natural language refinement)"*
3. Submit → enqueues `ai.generate_tests_from_spec` Celery task
4. UI shows "Generation in progress..." with a link to the review queue
5. When complete, candidates appear in the review queue (visible from a notification badge)

### 4.2 From a Test Case (Phase D)
Inside the Test Case editor, after the case is approved:
```
[Generate Selenium script from this case]
```

Same flow — generates an `AutomationScript` candidate, lands in review queue. The default target is Selenium Java for bank-facing E2E suites; Selenium Python remains selectable for prototypes and existing scripts.

### 4.3 From a Jira ticket (Phase D, simple) or the agent (Phase E, live)
Two paths:

**Phase D simple:** "Generate from Jira" button on the Specifications tab takes a ticket key, runs offline generation, lands candidates in review.

**Phase E live:** "Validate with agent" button starts a live agent session — the agent reads the Jira ticket, drives the app live, generates tests interactively. User watches via noVNC.

### 4.4 Trigger button rules
- Generation triggers go in their **most natural context**, not in a global "AI menu"
- Generate-from-spec lives on Specifications tab
- Generate-script lives in the Test Case editor
- Don't add an "AI" menu in the TopNav — it would invite asking "what AI features do I have?" which is the wrong mental model

---

## 5. The live agent view (Phase E)

This is the headline product experience. The user clicks "Author with agent" and watches the agent work.

### 5.1 The launcher
```
┌──────────────────────────────────────────────────────┐
│  AUTHOR WITH AGENT                                   │
│                                                      │
│  What should the agent do?                           │
│  ┌────────────────────────────────────────────────┐ │
│  │ Generate tests for the password recovery flow.│ │
│  │ Cover happy path, invalid email, expired token.│ │
│  │                                                │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  Source context (optional):                          │
│  ☐ Spec: Account Recovery Flow v2.3                  │
│  ☐ Jira: PROJ-456                                    │
│                                                      │
│  Target URL: [https://app.bank.local/recover]        │
│                                                      │
│                       [Cancel] [Start Agent]         │
└──────────────────────────────────────────────────────┘
```

### 5.2 The live view
After starting:

```
┌────────────────────────────────────────────────────────────┐
│  AGENT SESSION: 2026-05-07 10:23                           │
│  ┌──────────────────────────────┐  ┌─────────────────────┐│
│  │                              │  │ AGENT NARRATION    ││
│  │                              │  │                     ││
│  │   [browser pixels via noVNC] │  │ ▶ Reading spec...  ││
│  │   (always streaming)         │  │ ▶ Found 3 user    ││
│  │                              │  │   flows to test   ││
│  │                              │  │ ▶ Plan: visit     ││
│  │                              │  │   /recover         ││
│  │                              │  │ ▶ Action: click   ││
│  │                              │  │   "Forgot pwd"    ││
│  │                              │  │ ▶ Observed: form   ││
│  │                              │  │   appeared        ││
│  │                              │  │ ⟳ Generating step  ││
│  │                              │  │   3...             ││
│  └──────────────────────────────┘  └─────────────────────┘│
│                                                            │
│  [Pause] [Take over] [Cancel]                              │
└────────────────────────────────────────────────────────────┘
```

### 5.3 Agent narration events
The WebSocket carries new event types for agent sessions:
- `agent_thought` — internal reasoning
- `agent_decision` — chose an action
- `agent_action_attempted` — attempting in browser
- `agent_action_result` — observed outcome
- `agent_generated_step` — produced a TestCase step
- `agent_session_complete` — finished, candidates ready

The narration panel renders these as a styled timeline.

### 5.4 Take over (Phase E refinement)
The "Take over" button:
- Pauses the agent's loop
- The user's mouse and keyboard now control the browser via noVNC's bidirectional input
- The user can demonstrate something the agent missed
- Clicking "Resume agent" lets the agent continue with the new state

This is the KaneAI killer feature — *"the agent does 80% and the human takes over for the 20% it can't figure out."*

---

## 6. AI session history

Inside the AI tab:
```
┌──────────────────────────────────────────────────────┐
│  AGENT SESSION HISTORY                               │
│  ┌────────────────────────────────────────────────┐ │
│  │ 2026-05-07 10:23 — Banking App                 │ │
│  │ "Generate tests for password recovery flow"    │ │
│  │ Outcome: 3 candidates → all approved           │ │
│  │ Duration: 8m 12s                               │ │
│  │ [View session replay]                           │ │
│  └────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────┐ │
│  │ 2026-05-06 14:15 — Banking App                 │ │
│  │ "Validate transfer flow"                       │ │
│  │ Outcome: 1 failure → bug created in Jira       │ │
│  │ [View session replay]                           │ │
│  └────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

Session replay = noVNC video + step timeline + agent narration. Stored in MinIO.

---

## 7. The healing queue (Phase F)

When the agent proposes a selector fix with confidence below the auto-apply threshold:

```
┌──────────────────────────────────────────────────────┐
│  HEALING REVIEW QUEUE                                │
│                                                      │
│  Test: "User can submit transfer"                    │
│  Failed step: click "#confirm-button"                │
│                                                      │
│  Agent's proposed fixes:                             │
│  ┌────────────────────────────────────────────────┐ │
│  │ #1 (confidence: 87%)  ".confirm-action"        │ │
│  │     Visual match: ●●●●○                         │ │
│  │     DOM proximity: ●●●●●                        │ │
│  │ #2 (confidence: 65%)  "[data-test='confirm']"  │ │
│  │     Visual match: ●●●○○                         │ │
│  │     DOM proximity: ●●●●○                        │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│   [Apply #1] [Apply #2] [Manual fix] [Reject all]   │
└──────────────────────────────────────────────────────┘
```

Approving #1 writes the new selector back to the `AutomationScript`, recreates `HealingEvent` with status `applied`, resumes the failed execution.

---

## 8. Notifications and badges

Throughout the workspace:
- A badge on the AI tab when there are pending review items
- A toast when a generation task completes
- A persistent "Generation in progress" indicator while a task is running

These keep the user aware without being intrusive. They use the existing notification settings (`notification_provider` on `UserProfile`) to optionally route to Slack/Teams.

---

## 9. The configuration surfaces (manager-only)

The team manager configures AI in the Teams admin page:
```
Teams admin → Edit team → AI Configuration tab
  - Provider: [Anthropic ▼]
  - Test design model: [Claude Haiku ▼]
  - Execution model: [Claude Opus ▼]
  - API key: [••••••••••••] [Edit]
  - Monthly token budget: 5,000,000
  - Used this month: 1,234,000 (24%)
```

For an Ollama setup:
```
  - Provider: [Ollama (local) ▼]
  - Endpoint URL: [http://localhost:11434]
  - Test design model: [llama3:8b ▼]
  - Execution model: [llama3:70b ▼]
  - Monthly token budget: (unlimited for local)
```

Per-purpose model assignments live here. Individual users see no AI configuration in their profile.

---

## 10. The "Generate" affordance philosophy

Every AI generation action follows the same pattern:
1. **In-context trigger** — the button lives where the user is doing related work
2. **Optional refinement** — a small composer for natural-language context
3. **Async result** — task runs, user gets a notification on completion
4. **Review queue** — candidates accumulate, human approves before they become canonical
5. **Audit** — every generation is logged in MLflow + IntegrationActionLog

This pattern repeats across all Phase D and E features. New AI surfaces should fit the pattern. If a new feature can't, question whether it belongs here.

---

## 11. Why AI surfaces are last in the build order

Even though the AI features are the headline product, they ship last on the frontend because:
1. They depend on Phase D / E backend work — no point building UI for non-existent endpoints
2. They are richer than non-AI features and easier to overcomplicate
3. The non-AI workflows give us real users with real test data — that data is what makes AI demos compelling
4. Building UI for an unknown LLM output shape is wasteful; better to wire backend first, see what comes out, then design the UI to fit

The roadmap reflects this — see [`roadmap.md`](../roadmap.md). Frontend AI work begins after backend Phase D ships.
