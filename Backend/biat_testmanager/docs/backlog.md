# Backlog

Decisions that were intentionally deferred, not forgotten.
Each entry explains what was removed or skipped, why, and what the return should look like.

---

## Self-Healing Automation (HealingEvent)

**Removed in:** Phase 6.5 automation cleanup

**Why it was removed:**
The `HealingEvent` model existed as a placeholder table — it had fields, choices, and methods (`apply_fix`, `rollback`, `to_audit_log`) but nothing in the Playwright or Selenium runners ever created a record. It was dead infrastructure with no upstream writer and no downstream consumer.

**This was intentional. It was not forgotten.**

**What it should be when it returns:**

Self-healing is a real workflow, not just a log entry. When it comes back it should be modeled as a full pipeline:

1. **Detection** — during execution, a step fails because a selector is stale or a DOM element moved. The runner catches this and emits a healing trigger instead of immediately failing the step.
2. **Candidate generation** — an AI agent (vision, DOM diff, or hybrid) proposes one or more healed selectors with confidence scores.
3. **HealingEvent** — created at this point, status `PENDING`, with the original selector, candidate selectors, detection method, and confidence.
4. **Approval** — either auto-approved if confidence exceeds a threshold, or escalated to a human reviewer via the API.
5. **Application** — the approved selector is written back to the script or to a per-case selector override store.
6. **Audit** — the healing event is permanently recorded (applied, escalated, or rejected) and linked to the execution step and the test case revision it affected.

The model should gain:
- `status = PENDING` as the initial state (currently missing — only APPLIED / ESCALATED / REJECTED exist)
- `candidate_selectors` as a JSON field (one or more AI proposals, not just one healed_selector)
- `reviewed_by` FK to the user who approved or rejected
- `applied_to_revision` FK to the `TestCaseRevision` that was patched
- An explicit service layer: `propose_healing()`, `approve_healing()`, `reject_healing()`, `apply_healing_to_script()`
- API endpoints for the reviewer queue (list pending events, approve, reject)

**Target:** this belongs in a dedicated AI execution phase after the core non-AI platform is stable and the AI provider layer (`TeamAIConfig` / `ModelProfile`) is wired to a real inference call.
