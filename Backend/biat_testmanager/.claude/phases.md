# Phase status and plan

Single source of truth for what is built, what is planned, and what is deferred. Cross-references `docs/roadmap.md` (official step numbering) and the approved implementation plan.

## Quick map

| Phase / Step | Scope | Status |
|---|---|---|
| Step 1 — Queues + schema | Three Celery queues, model split | Built |
| Step 2 — Specs + RAG | SpecificationSource → Specification → SpecChunk, pgvector, BAAI/bge-m3 | Built |
| Step 3 — Selenoid + runners + MinIO | Selenoid hub, Java/Python runner Dockerfiles, MinIO artifacts | Built |
| Step 4A — Offline AI generation foundation | TeamAIConfig, ModelProfile, provider abstraction, AIGenerationSession, LangGraph 14-node graph | Built |
| **Phase D** — Test design quality (six sub-steps below) | Per-group fan-out, stronger extraction, coverage expansion + map, optional critic, diversity enforcement | **Designed, not yet implemented** |
| Step 4B — AI script generation | LLM produces Selenium scripts from logical cases | Not started |
| **Phase E** — Live agent (Playwright MCP browser authoring) | MCP stdio integration | **Foundation built; three follow-up steps planned** |
| Step 6 — Results Ingest API | External JUnit/Allure result intake | Not started |
| Step 7 — RCA | `TestResult.ai_failure_analysis` markdown | Not started (RCA is "smallest useful AI feature" in Phase D umbrella per `docs/architecture/07-ai-layer.md`) |
| Step 8 — GitHub sync (strict mode) | GitHub source-of-truth for scripts | Not started |
| Step 9 — GitHub PR + Jira automation | Webhook-driven PR validation, Jira-to-tests | Not started |
| **Phase F** — Self-healing | `HealingEvent` detection → candidate → approval → application | **Deferred** (spec in `docs/backlog.md`) |
| Step 11 — Moon + K8s | Replace direct Docker socket with Moon | Future |

## Phase D — Requirements → high-quality test design

**Status:** designed in plan, **do not implement** until explicitly approved per-step.

Phase D extends the existing 14-node generation graph (see [ai-layer.md](ai-layer.md)). None of the steps require new canonical models. The existing `AIGenerationSession` / `AIGenerationRetrievedContext` / `ai_generation_draft_v1` absorb the output. One new field is planned: `AIGenerationSession.coverage_map` (JSONField, D.4).

Phase D is **not optional and not a stepping stone to Phase E**. It is the core "requirements → reviewable logical test design tree" deliverable.

### D.1 — Per-requirement (or per-requirement-group) generation

Today: single LLM call generates the whole suite. With > ~5 requirements, attention budget thins and the output goes shallow ("3 vague tests").

Plan: replace `test_design_generator` (graph node 8) with a fan-out:
1. `partition_requirements` — heuristic grouping by actor / screen / API endpoint / business-rule cluster. Each group: ~3-5 requirements.
2. `generate_for_group` — run once per group with that group's requirement_extraction as focused context.
3. `merge_design` — dedupe scenarios/cases by title similarity + linked_requirement overlap.

Files: `apps/ai/graphs/test_generation_graph.py`, `apps/ai/services/test_generation_workflow.py`.

### D.2 — Stronger requirement extraction

Promote `requirement_extraction_v1` → `_v2` with explicit fields and few-shot examples from BIAT-flavored specs (bank product config, customer onboarding, transaction validation):

- `requirement_ids` (when present in spec — e.g., RX-12, BR-105)
- `acceptance_criteria` (verbatim where available)
- `actors` and `roles`
- `screens` (UI) and field-level details per screen
- `api_endpoints` touched
- `business_rules` (with `rule_id` when present)
- `validation_rules` (per field, per form)
- `generated_outputs` (reports, notifications, files)
- `error_conditions` and their expected messages
- `open_questions` — anything the spec implies but doesn't state

Few-shot makes the difference between empty arrays and structured facts the design node can ground on.

Files: `apps/ai/prompts/requirement_extraction_v1.py` → new `requirement_extraction_v2.py`.

### D.3 — Coverage expansion (do not just copy the spec)

The generated set must add value, not echo the spec. Enforce in the design prompt and validate in the quality gate:

- ≥1 `HAPPY_PATH` (positive) per requirement
- ≥1 `ALTERNATIVE_FLOW` per business rule with branches
- ≥1 `EDGE_CASE` AND ≥1 `NEGATIVE`-polarity case per validation rule
- ≥1 `SECURITY` case per role/permission boundary (logged-out, wrong role, expired token)
- ≥1 `PERFORMANCE` case when the requirement mentions bulk / large file / batch
- `ACCESSIBILITY` cases only when the spec explicitly references ARIA / WCAG / screen-reader / keyboard navigation — do not invent
- Anything the spec is silent on → `open_questions`, **not** a guessed test case

Files: `apps/ai/prompts/test_design_v1.py` — add an explicit "coverage mandate" block.

### D.4 — Coverage map (per requirement)

After draft generation, build a coverage map keyed by requirement (by ID or extracted phrase):

- `covered_by` — generated case `draft_id`s testing it, with confidence
- `weakly_covered` — cases that touch but don't fully exercise
- `uncovered` — requirements with no generated case
- `ambiguous` — requirements where extraction flagged missing details (linked to `open_questions`)
- `duplicates_in_repository` — existing canonical TestCase IDs (from repository memory search) already covering this requirement

Persist on the session as `AIGenerationSession.coverage_map` (new JSONField, new migration). Render in the review drawer so the human sees gaps and overlaps before committing.

Files: new `coverage_mapper` node in the graph; new field on the session; new section in `frontend/src/components/project/ai/AIGenerationPanel.tsx`.

### D.5 — Optional critic pass (gated by model quota)

The `test_critic` node (graph node 13) is already wired — `AI_GENERATION_ENABLE_CRITIC=False` today. Re-enable conditionally; rewrite the critic prompt to judge **added coverage value vs. mere paraphrase of the requirement**.

Output should:
- Flag `low_value` cases (reviewer should drop) with a reason
- Suggest missing case types per requirement (consumed back into D.3 as a regeneration hint)
- Score the overall draft on a 0-10 "non-trivial coverage" axis, persisted on the session

Gate by quota: if the team's `review` ModelProfile has remaining quota (e.g., GitHub Models GPT-4o daily budget), run the critic; otherwise skip with `quality_warnings += ["critic skipped: review profile quota exhausted"]`. Never block on critic absence.

Files: `apps/ai/prompts/test_critic_v1.py`, graph node, new setting `AI_GENERATION_CRITIC_MODE ∈ {off, when_available, required}`.

### D.6 — Diversity enforcement on scenario_type and polarity

In practice the LLM produces ~90% `HAPPY_PATH` / `POSITIVE`. Extend `draft_quality_gate`:

- If a scenario_type quota mandated by D.3 isn't met → **targeted regeneration prompt for just the missing type** (not a full re-design — much cheaper).
- Track every forced regeneration in `quality_warnings` so the reviewer sees what was enforced.
- Idempotent: a regeneration pass that still fails marks it as `open_question` rather than looping.

Files: `apps/ai/services/draft_quality.py` — extend `evaluate_draft_quality`, add `regenerate_missing_types` helper.

### Phase D verification (when implemented)

- `uv run python manage.py test apps.ai.tests.test_generation_workflow --keepdb` — extend with per-group fan-out, coverage map persistence, critic-skipped-on-no-quota, diversity enforcement, dedup-against-repository.
- Manual: generate from a real BIAT spec (e.g., a product onboarding doc); confirm ≥1 EDGE_CASE per validation rule, ≥1 NEGATIVE per business rule, no fabricated ACCESSIBILITY cases, coverage map renders with at least one `weakly_covered` and one `open_question`.

## Phase E — Browser authoring next 3 implementation steps

**Scope reminder:** Phase E takes **one selected logical TestCase** Phase D produced and a human approved, drives Playwright MCP to record actions, saves trace as a draft `TestCaseRevision`. Phase E does not generate test design.

### Step 1 — Make the browser-authoring LLM call cost-stable and deterministic

File: `apps/ai/services/browser_authoring.py` (function `_next_browser_action`)

1. Pin `max_tokens=250` and `temperature=0` on the provider.chat call. Both OpenAI-compatible (`temperature` in body) and Ollama (`options.temperature`) already pass it through. Schema's strict shape means 250 is plenty.
2. Cap observation payload sent to the LLM (not at the tool — the full snapshot still gets recorded for save-trace):
   - `snapshot` truncated to ~1500 chars (head-kept, tail elided)
   - `interactive_elements` truncated to ~30 entries (those near goal/trace elements; otherwise first 30)
   - `visible_text_summary` left as-is
3. Verify `OpenAICompatibleProvider.post_json` retries Groq 429 honoring `retry-after`. Bump `max_retries` to 2 for the `EXECUTION` purpose if Groq cooldowns regularly exceed one retry.

Verification: extend `test_browser_authoring.py` asserting `max_tokens=250`, `temperature=0`, and truncation length reach the fake provider.

### Step 2 — Containerized Playwright MCP with VNC, into the existing live-viewer pipeline

Goal: live viewer shows the real browser via the existing `NoVncViewer` component — same Channels consumer, same stream-ticket flow as Selenoid runs.

Pieces:
1. Docker image: "Playwright MCP + Xvfb + x11vnc + websockify" (or community equivalent). Build from `mcr.microsoft.com/playwright:focal` + `x11vnc` + `websockify`.
2. MCP transport: keep `stdio_client` but launch MCP inside the container via `docker run -i ... npx @playwright/mcp@latest --browser chromium` (no `--headless`). Container exposes VNC on a dynamically allocated port. (Alternative: switch to HTTP/SSE MCP transport if/when Playwright MCP supports it.)
3. Backend wiring:
   - New module `apps/automation/services/mcp_browser_sessions.py` (or extend `browser_sessions.py`). Per-session container allocator: picks free port, runs `docker run -d -p <port>:5900 --name biat-mcp-<exec_id> biat-playwright-mcp:latest`, returns `(session_id=container_id, vnc_url=ws://host:<port>/websockify)`.
   - `PlaywrightMCPBrowserAuthoringTool.start()` calls allocator before stdio init; `get_stream_session_id()` returns the container id.
   - `_cache_session_if_available` (already writes `selenium_session_id` + caches URLs) reuses the existing path. Repurpose the field name to avoid a migration.
   - `BrowserStreamConsumer` proxies frames from `ws://host:<port>/websockify`.
   - `tool.close()` must stop and remove the container in `finally`.
4. Settings: add `AI_PLAYWRIGHT_MCP_RUNNER_IMAGE`, `AI_PLAYWRIGHT_MCP_VNC_PORT_RANGE` (e.g. `5900-5910`), `AI_PLAYWRIGHT_MCP_DOCKER_NETWORK` (likely `biat_selenoid` so the consumer can resolve container DNS in dev). Add a `docker-compose.ai-mcp.yml` (or fold into `docker-compose.selenoid.yml`).
5. Frontend: no changes. `NoVncViewer` already handles "stream ticket → WebSocket". "No browser session active" becomes the empty state for QUEUED / finished sessions only.

Why this shape: AI authoring becomes a first-class execution citizen, reuses every piece of streaming/checkpoint/control plumbing, lands on the same rails Phase E roadmap step plans. The screenshot-stream alternative would build a throwaway second viewer.

Verification: new `test_browser_authoring_vnc.py` mocks the Docker allocator; manual OrangeHRM authoring run confirms the live viewer shows the real browser.

### Step 3 — Harden the authoring task surface and tighten save-trace UX

Backend:
1. Wrap top of `run_browser_authoring_session` with `TestExecution.DoesNotExist` guard — stale Celery tasks ack and log, not crash the worker.
2. Wrap `enqueue_authoring_session_task(...)` inside `start_browser_authoring_session` with `transaction.on_commit(...)`.
3. Same `DoesNotExist` guard in `_run_authoring_session` (`apps/ai/tasks.py`).
4. In `_cache_session_if_available`, also publish a `status_changed` event with the new `selenium_session_id` so executionStore picks it up without polling.

Frontend:
1. Confirm dialog before `saveAIAuthoringTrace`: "This will replace the steps on this test case and reset its design status to DRAFT. A new revision will be created."
2. Show `mutation_source: "ai_browser_authoring_trace"` provenance in the case history tab.

Verification: extend `test_browser_authoring.py` with (a) stale-ID test, (b) on_commit enqueue test, (c) `status_changed` publish with session_id.

## Phase F — Self-healing (deferred)

Full spec lives in `docs/backlog.md`. Summary:

1. **Detection** — runner catches `NoSuchElementException` (or equivalent) → emits `healing_triggered` event instead of `step_failed`.
2. **Candidate generation** — `LangGraph healing_node`: gets DOM snapshot, proposes candidate selectors with confidence scores.
3. **HealingEvent (PENDING)** — model rebuilt per the backlog spec.
4. **Approval** — auto-approve when confidence > threshold; otherwise escalate via `ExecutionCheckpoint`.
5. **Application** — approved selector written back to the `AutomationScript`.
6. **Audit** — `IntegrationActionLog` entry for traceability.

Not before Phase D ships and Phase E is solid.

## Decisions already made (do not relitigate)

From `docs/PLATFORM.md` and `docs/roadmap.md`:

- Selenium = firm's deterministic test execution engine (Layer 2). Playwright = AI agent's interface only (Layer 3, via Playwright MCP).
- Selenium Grid on-premises (firm's server) — no cloud infra needed.
- LangGraph agent drives Playwright live → outputs Selenium script → Grid executes it.
- AI config (`TeamAIConfig` + `ModelProfile`) is data-driven; new providers do not require code changes.
- GitHub source-of-truth for scripts in strict mode (Phase E follow-up); lax mode with personal tokens is future.
- HMAC-SHA256 mandatory on all webhooks. Unsigned webhooks rejected without processing.
- `HealingEvent` belongs in Phase F, not before.
- Moon + K8s migration is Step 11. Until then, Docker socket coupling is acceptable.
