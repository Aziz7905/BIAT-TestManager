# 01 — Product Vision

**What we are building. What we are deliberately not building. The KaneAI comparison.**

---

## 1. The one-line product statement

BIAT TestManager is **KaneAI for the bank**: an AI-native QA platform that lives inside BIAT's network, runs on Docker (not a 3000-browser cloud), and gives a single QA team the full KaneAI workflow — Jira ticket to test case, GitHub PR to validation, broken selector to self-healing fix.

---

## 2. The mental model: TestRail, HyperExecute, KaneAI

Three reference platforms exist on the market. We borrow concepts from each:

| Reference platform | What it is | What we take from it |
|---|---|---|
| **TestRail / qTest** | Pure test management. No execution. Stores cases, plans, runs, results. | Layer 1 — the data spine of the platform. Plans, runs, cases, traceability. |
| **LambdaTest / TestMu / HyperExecute** | Cloud test execution at scale. 3000+ browsers, device farms, massive parallelism. | Layer 2 — the *concept* of dispatching scripts to a remote browser pool. We do the small version: a few Docker browser nodes on-premise. |
| **KaneAI** | AI agent that reads requirements, generates tests, drives a browser live, self-heals. The "agentic" layer. | Layer 3 — the entire AI agent surface. This is the headline feature. |

We are not trying to compete with any of them on scale. We are trying to assemble the **smallest correct version** of all three, in one product, that fits inside a bank.

---

## 3. What KaneAI does (and what we therefore must do)

### 3.1 KaneAI's Jira loop
1. KaneAI reads a Jira ticket (summary, description, comments, attachments).
2. It generates end-to-end test cases that cover the requirement.
3. The user reviews the candidates, accepts the good ones.
4. Accepted cases enter the canonical test repository.
5. Tests can later be linked back to the Jira ticket for traceability.
6. If a test fails, KaneAI can create a Jira bug with screenshot + logs + RCA.

### 3.2 KaneAI's GitHub loop
1. The LambdaTest GitHub App watches pull requests.
2. On a PR, the agent analyzes the diff to understand what changed.
3. The user comments `@KaneAI Validate this PR`.
4. The agent either authors new tests for the changes or selects existing relevant tests.
5. Tests run on HyperExecute.
6. Results + RCA are posted back to the PR as a comment.

### 3.3 KaneAI's authoring loop
1. The user types a test in natural language: *"log in, navigate to transfers, send 100 TND, verify the receipt page"*.
2. The agent translates that into structured steps.
3. The agent drives a browser live (the user watches via noVNC) to record actions for ambiguous steps.
4. The recording is translated into a Selenium script: Java by default for bank-facing suites, Python when selected for dev/prototype scripts.
5. The script is saved as an `AutomationScript` candidate, reviewed, approved.

### 3.4 KaneAI's self-healing
1. During a regression run, a step fails because a selector broke (UI changed).
2. Instead of just failing, the agent inspects the DOM and proposes new selectors with confidence scores.
3. If confidence is high enough, the test resumes with the new selector.
4. The fix is written back to the script (or to a per-case selector override store).
5. If confidence is low, the agent escalates to a human via a checkpoint.

### 3.5 KaneAI's RCA
1. A test fails.
2. The agent gathers the exception, the DOM snapshot at failure, the step history, the recent code diffs.
3. The LLM produces a human-readable explanation: *"The login button moved from `#submit` to `.btn-primary` between commit X and commit Y."*
4. The RCA is attached to the failure record and posted to GitHub/Jira.

**All five loops are in scope for BIAT TestManager.** They are the product. The layers below them (test management, regression execution) exist to make these loops possible.

---

## 4. What we deliberately are NOT building

These are common things that look like they belong in a QA platform but are explicitly out of scope:

### 4.1 We are not HyperExecute
- No 3000+ browser combinations
- No device farm (no real iOS/Android devices)
- No global multi-region deployment
- No cross-browser farm with 100+ Chrome/Firefox/Safari/Edge variants
- No autoscaling worker pools across cloud regions

We have a **handful of Docker Chrome nodes** on the bank's network. That's the regression engine. If parallelism is needed beyond what one server can give, we move to Moon + Kubernetes — but that's much later.

### 4.2 We are not LambdaTest's marketing surface
- No Smart UI visual regression with pixel-perfect baselines
- No real-device fingerprinting
- No accessibility-checking AI
- No native performance/load test engine
- No native API/unit/integration runtime engine
- No native security testing engine (DAST/SAST)

Those test categories can still be represented as managed test assets and ingested results. The boundary is runtime ownership: existing bank infrastructure can run them, BIAT can consume and report their outputs.

### 4.3 We are not a CI/CD replacement
Engineers who write Selenium scripts in their IDE and run them via Jenkins keep doing that. The platform's Selenium Grid URL is reachable from Jenkins — it's just a remote driver endpoint. We don't replace anyone's pipeline. We integrate with it (see [`08-integrations.md`](08-integrations.md)).

### 4.4 We are not a generic AI assistant
- No "ask Claude anything" chat
- No code review for the engineer's other repos
- No generic developer copilot

The AI agent in this platform has **one job**: produce, run, maintain, and repair tests for the BIAT applications.

---

## 5. The two execution paths (resolving a common confusion)

A frequent confusion: *if the platform stores Selenium scripts in `AutomationScript`, are they executed on the platform or do engineers run them in their IDE / Jenkins?*

The answer is **both paths are supported, simultaneously, on the same `AutomationScript` record:**

### Path A — Platform-executed (the KaneAI path)
```
Tester writes script in platform code editor (or AI generates it)
         ↓
AutomationScript stored in DB
         ↓
Tester triggers run from UI
         ↓
Celery dispatches to Selenoid (or Selenium Grid until the migration is complete)
         ↓
Script runs in a Docker runner container
         ↓
Results, steps, artifacts come back to the platform
```

### Path B — CI/CD-executed (the engineer's path)
```
Engineer writes script in IDE (PyCharm / VSCode)
         ↓
Commits to GitHub
         ↓
GitHub Actions / Jenkins runs the suite
         ↓
Script points at the platform's browser backend as remote driver, or runs entirely on existing CI/lab infrastructure
         ↓
Grid executes it
         ↓
Results reported back to platform via API
```

Both paths feed the same `TestResult` records. The platform is **either** the orchestrator (Path A) **or** a results sink plus, optionally, a remote browser farm (Path B). The engineer chooses per script.

The AI agent's output (Layer 3) goes through Path A by definition — generated scripts are saved as `AutomationScript` candidates and run on the platform.

---

## 6. Why this matters: the difference from "just a wrapper"

If we were building a plain wrapper around Selenium Grid, this product would already exist (it's called Selenium Grid). The thing that makes BIAT TestManager useful and worth building is the combination:

- **Layer 1** gives the bank a real test management system instead of a spreadsheet
- **Layer 2** gives the bank a place to actually run those tests without depending on each engineer's laptop
- **Layer 3** gives the bank an AI agent that reads its Jira board, watches its GitHub PRs, and writes/maintains the tests automatically

Each layer alone is a "nice to have." All three together is **the bank's complete QA workflow in one tool**, with no SaaS subscription, no data leaving the network, and no per-seat license fee scaling with the team.

---

## 7. The audience

The platform is built for three roles inside the bank's QA function:

| Role | What they do on the platform |
|---|---|
| **QA Manager** | Configures the team's AI provider, integrations, project membership. Reads dashboards. Approves AI-generated test candidates. Sets concurrency budgets per project. |
| **QA Engineer (manual)** | Writes test cases, organizes them in suites/sections/scenarios, plans runs. Marks manual test executions pass/fail. Reviews AI-generated tests. |
| **QA Engineer (automation)** | Writes Selenium Java/Python scripts — either in the platform editor or in their IDE. Triggers regression runs. Debugs failures. Maintains the regression suite. |

There is **no** "developer" role on the platform. Developers interact with the platform indirectly through GitHub PRs and Jira tickets — the AI agent reads from those interfaces. Developers never log into the platform.

---

## 8. Scale targets

This is the scale we are building for, not aspirational scale:

| Dimension | Target |
|---|---|
| Total users | ~20–50 (one bank QA team) |
| Concurrent active users | ~10–15 |
| Projects | ~5–20 (one per banking app / module) |
| Test cases stored | 10,000–50,000 |
| Concurrent test executions | 3–10 (Selenium Grid + Selenoid combined) |
| Concurrent AI agent sessions | 1–3 |
| Specifications indexed | 1,000–5,000 documents |

Anything beyond this scale is a future migration concern (Moon + Kubernetes, see [`05-execution-engine.md`](05-execution-engine.md)). The current architecture is sized for the above and no more.

---

## 9. Why on-premise (and not cloud)

Bank. That's the answer.

- Data residency: Tunisian banking regulations require customer data to stay in-country
- Test data sometimes mirrors production data (anonymized) — cannot leave the bank's network
- Specifications often contain business-confidential information
- The bank already runs Docker workloads in its data center; the marginal cost of adding a few Chrome containers is zero
- No procurement headache for SaaS approvals

This is also why we use **MinIO** (self-hosted S3-compatible storage) instead of AWS S3 / Azure Blob, and **Ollama** (local LLM) as the default AI provider option alongside cloud APIs.

---

## 10. The "build vs buy" answer

The bank could buy LambdaTest. Why build BIAT TestManager instead?

| Concern | Buying LambdaTest | Building BIAT TestManager |
|---|---|---|
| Per-user cost | Scales linearly with QA headcount | Zero |
| Data leaves the network | Yes (US-based SaaS) | No |
| Customization for BIAT-specific Jira/GitHub workflows | Limited | Full control |
| Tunisian Arabic language support in AI generation | Generic English-first | Trainable, prompt-tunable to BIAT context |
| Vendor lock-in | High | None |
| Initial build cost | Subscription | One-time engineering investment |
| Dependence on internet connectivity | Required | Works fully offline |

The build is a one-time investment. The buy is a recurring rent. For a bank with stable internal infrastructure and a need for data sovereignty, the build wins.

---

## 11. What success looks like

Concretely, the platform is "done" (v1) when a QA team member can:

1. Open a Jira ticket in the platform
2. Click "Generate tests"
3. The AI reads the ticket, the linked specs, and the existing test repository
4. The AI generates 5 candidate test cases
5. The user reviews them, edits one, approves three, rejects two
6. The approved cases enter the canonical repository
7. The user clicks "Generate automation script" on each case
8. The AI writes Selenium scripts; the user reviews them
9. The user clicks "Run" — the scripts execute on the regression Grid
10. Two pass, one fails
11. The AI generates an RCA explaining the failure
12. The AI either self-heals the broken selector or creates a Jira bug

That entire loop runs inside the bank's network, with no data leaving, in roughly 10–20 minutes of human attention.

That's the product.
