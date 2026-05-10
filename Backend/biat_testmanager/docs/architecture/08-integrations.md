# 08 — Integrations

**GitHub source-of-truth sync. Jira ticket → test generation. Webhook ingestion. HMAC signatures. Action audit.**

---

## 1. The four integration responsibilities

The platform integrates with three external systems: **Jira**, **GitHub**, **Jenkins**. Each integration covers up to four responsibilities:

| Responsibility | Jira | GitHub | Jenkins |
|---|---|---|---|
| Ingest events (webhooks) | ✓ (issue events) | ✓ (PR, push events) | ✓ (build events) |
| Read external state (API calls) | ✓ (read tickets) | ✓ (read PRs, diffs) | ✓ (read builds) |
| Write external state (API calls) | ✓ (create bugs, post comments) | ✓ (post PR comments) | ✗ (read-only for now) |
| Sync content (continuous) | ✗ | ✓ (script files) | ✗ |

The most important and most powerful integration is **GitHub** because it is the source of truth for `AutomationScript` content when engineers prefer their IDE over the platform editor.

---

## 2. The data model (already built)

The integration foundation is in place. See [`03-domain-model.md`](03-domain-model.md) for full details.

| Model | Purpose |
|---|---|
| `IntegrationConfig` | Per-team or per-project encrypted JSON config (URLs, project keys, webhook secrets) |
| `UserIntegrationCredential` | Per-user encrypted personal credentials (act-as-user tokens). Never returned by API |
| `RepositoryBinding` | Links a project to an external code repository |
| `WebhookEvent` | Durable record of every webhook delivery, signature-verified |
| `ExternalIssueLink` | Connects Jira/GitHub issues to project objects |
| `IntegrationActionLog` | Append-only audit trail of every external API call |

What's NOT yet built: the **reactive logic** that consumes these records. Webhooks are stored, but nothing reacts to them yet. Results ingest, GitHub sync, and AI-powered Jira/GitHub flows are sequenced separately in the roadmap.

---

## 3. HMAC signature verification

### 3.1 The rule
**Every webhook delivery must be HMAC-SHA256 signed.** Unsigned or mismatched-signature requests are stored with `signature_status='rejected'` and never trigger downstream processing.

### 3.2 Signature headers
| Provider | Header | Format |
|---|---|---|
| GitHub | `X-Hub-Signature-256` | `sha256=<hmac_hex>` |
| Jira | `X-BIAT-Signature-256` | `sha256=<hmac_hex>` |
| Jenkins | `X-BIAT-Signature-256` | `sha256=<hmac_hex>` |

### 3.3 Verification flow
```
Webhook arrives
       ↓
Backend reads raw body and the signature header
       ↓
Backend reads the relevant IntegrationConfig.webhook_secret
       ↓
Computes hmac_sha256(secret, body) and compares to header value
       ↓
If match: WebhookEvent(signature_status='verified', payload_json=body)
If no match: WebhookEvent(signature_status='rejected', payload omitted)
       ↓
Verified events are eligible for downstream processing
Rejected events are visible only to platform admins for diagnosis
```

### 3.4 Why this is non-negotiable
Without HMAC, anyone with the webhook URL can forge events. For a system that automatically generates test cases from Jira tickets and triggers regression runs from GitHub PRs, that's catastrophic. Signature verification is the **first line of defense.**

---

## 4. GitHub source-of-truth sync (the big one)

### 4.1 The problem
Engineers write Selenium scripts in their IDE. They commit to GitHub. The platform's `AutomationScript.script_content` should match GitHub. If they drift, the platform is running an outdated script and reporting bogus results.

### 4.2 The solution
Treat GitHub as the canonical source for any script that has a `RepositoryBinding`. The platform's `AutomationScript.script_content` is a **cached copy** that's updated automatically on push.

### 4.3 The required fields on `AutomationScript`

```python
class AutomationScript(models.Model):
    # ... existing fields ...

    # NEW (planned, Step 8 in roadmap):
    source_repo_binding = models.ForeignKey(
        RepositoryBinding,
        null=True, blank=True,
        on_delete=models.SET_NULL,
    )
    source_repo_path = models.CharField(max_length=500, blank=True)  # e.g. "tests/login_test.py"
    pinned_commit_sha = models.CharField(max_length=40, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
```

If `source_repo_binding` is set, the script is GitHub-backed. Editing it in the platform UI either:
- (Strict mode) is disabled — UI shows "this script is GitHub-backed; edit in GitHub"
- (Lax mode) creates a new commit on the user's behalf via GitHub API

Default: strict mode. Lax mode is a future enhancement requiring `UserIntegrationCredential`.

### 4.4 The sync flow

```
Engineer pushes to GitHub
       ↓
GitHub sends push webhook → /webhooks/github/
       ↓
HMAC verified → WebhookEvent(signature_status='verified')
       ↓
Webhook consumer (new, in apps/integrations/services/github_sync.py):
   1. Parse the push event — find the changed files
   2. For each changed file path:
       a. Look for AutomationScript(source_repo_path=path,
          source_repo_binding__repo_full_name=repo_name)
       b. If found:
          - Fetch the new file content via GitHub API
          - Update AutomationScript.script_content
          - Update pinned_commit_sha = head_commit_sha
          - Update last_synced_at = now()
   3. IntegrationActionLog entry written for each sync
       ↓
The next regression run uses the updated script automatically
```

### 4.5 The pull (manual) flow
For initial setup or recovery, a user can trigger a manual sync from the UI: "Pull from GitHub." Same logic, runs synchronously.

### 4.6 Conflict handling
Strict mode means the platform never writes back to GitHub. So conflicts can only happen in one direction: GitHub has a new version, the platform's cached copy is stale. The webhook handler simply overwrites the platform's copy. No conflict resolution needed.

If lax mode is ever enabled, two-way edits introduce conflicts that need a real merge strategy. That's a future problem.

---

## 5. Jira ticket → test generation

### 5.1 The flow (Phase D, with AI)
```
User opens a Jira ticket reference inside the platform
       ↓
User clicks "Generate tests from this ticket"
       ↓
Backend:
  1. Resolve the team's Jira IntegrationConfig (base_url, project_key)
  2. Fetch the ticket via Jira API:
     - summary, description, comments, attachments
  3. Resolve associated specs (if linked) for RAG context
  4. Build LLM prompt including ticket + RAG specs
  5. LLM generates candidate TestCases
  6. Each candidate gets ExternalIssueLink created
     - links the new TestCase to the Jira ticket
       ↓
User reviews candidates → approves → cases become canonical
The Jira link survives — the test is now traceable to the requirement
```

### 5.2 The reverse direction: bug creation
```
A regression test fails
       ↓
RCA generated (Phase D)
       ↓
User clicks "Create Jira bug from this failure"
       ↓
Backend:
  1. Resolves Jira IntegrationConfig
  2. Calls Jira API to create issue:
     - summary = "Regression failure: <test name>"
     - description = test steps + error + RCA
     - attachments = failure screenshot, video URL (pre-signed MinIO URL)
  3. Creates ExternalIssueLink(provider='jira', target=test_execution)
  4. Logs to IntegrationActionLog
       ↓
The Jira ticket is now linked back to the failed execution — closing the loop
```

### 5.3 Webhook reaction (auto-generation)
A future Phase E feature: when a Jira webhook fires for a new issue with a specific label (e.g., `qa-required`), the agent can automatically generate test candidates without the user clicking anything. The candidates land in the review queue waiting for human approval.

---

## 6. GitHub PR → test selection / generation (KaneAI feature)

### 6.1 The KaneAI behavior we replicate
> "By adding a comment like @KaneAI Validate this PR, you trigger the AI to author new tests for the changes or select relevant existing tests from your inventory to run. Results and AI-powered root cause analysis (RCA) are posted directly back to the GitHub PR as comments."

### 6.2 The flow (Phase E)
```
PR opened or updated
       ↓
GitHub webhook fires → /webhooks/github/
       ↓
WebhookEvent stored, signature verified
       ↓
A reviewer comments "@biat validate this PR"
       ↓
GitHub issue_comment webhook fires → /webhooks/github/
       ↓
Backend webhook consumer detects the trigger phrase
       ↓
Celery task on `ai_agent`:
   1. Read PR diff via GitHub API
   2. RAG-search the test repository:
      - Which tests cover the modified components?
      - Are there gaps?
   3. Decide: select existing tests, generate new ones, or both
   4. If new tests needed: agent session in Selenoid generates them
   5. Trigger regression run on selected tests
   6. Wait for results
   7. If failures: generate RCA per failure
   8. Compose a markdown comment summarizing:
      - Tests that ran (passed/failed)
      - RCA for each failure
      - Pre-signed URLs to videos for each failure
      - Suggested fixes if any
   9. Post the comment to the PR via GitHub API
   10. IntegrationActionLog entry
```

### 6.3 Why this is the headline feature
This is the moment the product proves its worth: **a developer opens a PR and the platform automatically tells them whether it broke anything, what broke, and why** — all without leaving GitHub. That's KaneAI's core value, replicated.

---

## 7. Jenkins integration (lighter scope)

### 7.1 Today
- `IntegrationConfig` for Jenkins URL + webhook secret
- Webhooks ingest build events
- No reactive logic yet

### 7.2 Two use cases
**Inbound (Jenkins → BIAT):**
- A Jenkins job runs nightly regression
- On completion, Jenkins posts a webhook to BIAT
- BIAT records the run as a `TestRun(trigger_type='nightly', run_kind='system_generated')` and stores the result

**Outbound (BIAT → Jenkins):** Out of scope for the foreseeable future. Triggering Jenkins jobs from BIAT would invert the integration — Jenkins is meant to drive automation, not be driven.

### 7.3 The realistic Jenkins scenario
Most likely: Jenkins runs an existing test suite and reports results back via the BIAT REST API. For browser E2E, the suite may point its `RemoteWebDriver` at the BIAT browser backend; for performance, security, API, unit, and integration tests, Jenkins or another bank-owned tool remains the runtime engine and BIAT is the management/results layer.

```
POST /api/test-results/external/
  - run_id (or auto-create one with run_kind='system_generated')
  - case_id (matches a TestCase by external_id or name)
  - status, duration_ms, error_message, junit_xml, video_url
```

The endpoint is authenticated with a per-team API key. Results land in the platform's normal data model.

This isn't built yet but is straightforward when needed.

---

## 8. Personal credentials (`UserIntegrationCredential`)

### 8.1 What they are
Sometimes a user wants to act as themselves on Jira/GitHub instead of as the team's shared service account. For example: when creating a Jira bug from a failure, the bug should be authored by the user, not by `biat-bot`.

For these flows, the user stores a personal token in `UserIntegrationCredential`. The platform uses it for that specific user's actions.

### 8.2 The rules
- Tokens are encrypted at rest (`FIELD_ENCRYPTION_KEY`)
- Tokens are **never** returned by any API serializer
- Frontend can only check `has_jira_token: bool`, etc.
- A user can rotate or delete their token at any time
- Removing a user → cascade delete their credentials

### 8.3 Default fallback
If a user has no personal credential, the team's shared `IntegrationConfig` credential is used. The action is logged as performed by the user but executed via the team account.

---

## 9. Audit trail (`IntegrationActionLog`)

Every external API call writes a row:
```python
class IntegrationActionLog(models.Model):
    provider = models.CharField(...)         # "jira" | "github" | "jenkins"
    action = models.CharField(...)           # "create_issue" | "post_comment" | "fetch_diff" | ...
    target = models.CharField(...)           # external id or URL
    status = models.CharField(...)           # "success" | "failure"
    actor_user = models.ForeignKey(User, null=True)
    request_summary = models.JSONField(...)  # truncated for audit, no large payloads
    response_summary = models.JSONField(...)
    timestamp = models.DateTimeField(auto_now_add=True)
```

### 9.1 What goes in `request_summary` / `response_summary`
- HTTP method, URL, status code
- A summary of the body — **not** the full body for large requests
- Error messages on failure

### 9.2 What's intentionally NOT in here
- API tokens or any credentials
- Full webhook payloads (those live in `WebhookEvent`)
- Personally identifying data beyond `actor_user`

### 9.3 Retention
- Default retention: indefinite (audit-required)
- The bank's audit team can query by user, by provider, by date range

---

## 10. The integrations app boundary

`apps/integrations/` owns:
- The models above
- The webhook ingestion endpoints
- HMAC verification
- Adapter classes for each provider (Jira API, GitHub API, Jenkins API)

It does **not** own:
- The AI agent (that's `apps/ai/`)
- The execution pipeline (`apps/automation/`)
- The test repository (`apps/testing/`)

When the AI agent needs to read a Jira ticket, it imports a function from `apps.integrations.services.jira` — the integrations app provides clean adapters that the AI app consumes. The AI app doesn't talk directly to provider SDKs.

This separation means: if Jira ever breaks or BIAT switches to a different ticket system, you change adapter code in one place. The AI prompts and the test generation logic don't change.

---

## 11. The current state vs the next state

| Capability | Today | Next roadmap step |
|---|---|---|
| Webhook ingestion + HMAC | Built | (no change needed) |
| `IntegrationConfig`, `RepositoryBinding`, etc. | Built | (no change needed) |
| GitHub push → AutomationScript sync | Not wired | Step 8 |
| Jira ticket → AI test generation | Not wired | Step 9 after Phase D/E AI plumbing |
| GitHub PR → AI validation | Not wired | Step 9 after Phase E agent |
| Jenkins/external result ingestion | Not built | Step 6 |
| Cross-provider audit log | Built | (no change needed) |

The infrastructure is solid. The reactive consumers are what's missing. They're sequenced in the roadmap to align with execution and AI phases: Results Ingest first, GitHub source sync later, then AI-powered Jira/GitHub features once Phase D/E are online.
