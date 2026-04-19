# BIAT TestManager Master Roadmap

Last updated: 2026-04-19

This is the master product note for BIAT TestManager.

It explains:

1. what we have built so far
2. what the current platform can really do
3. what is still missing
4. what we want the product to become later
5. the order in which we should build the next layers

This file is intentionally product-level and architecture-level.
More specific notes remain in the other docs under `docs/architecture/`.

## 1. Product objective

BIAT TestManager is being built as a serious test management platform first, with AI layered on top later.

The long-term goal is:

- manage requirements and specifications
- design structured test repositories
- preserve revision-safe test assets
- plan and run tests
- execute UI/E2E automation
- inspect results, artifacts, and reporting
- later add reviewed AI generation and remote interactive execution

The platform should remain useful even without AI.

## 2. Core principles

These principles have guided the work so far:

- the platform must work without AI
- stable domain models come before flashy AI features
- views stay thin
- serializers validate and map data
- services hold workflow and business logic
- design-time data, revision data, execution data, and integration data stay separated
- AI should layer on top of the platform, not replace the platform

## 3. What we have built so far

### 3.1 Accounts, tenancy, and permissions

The access model is already in place:

- `Organization`
- `Team`
- `TeamMembership`
- `Project`
- `ProjectMember`
- `UserProfile.organization_role`

Authority is no longer based on legacy compatibility fields.

This gives us the non-AI permission backbone for the whole platform.

### 3.2 AI and integration configuration

We already separated future configuration concerns into explicit models:

- `TeamAIConfig`
- `ModelProfile`
- `IntegrationConfig`
- `UserIntegrationCredential`

This matters because future AI generation and external integrations will plug into the platform cleanly instead of leaking into unrelated models.

### 3.3 Specifications and retrieval

The specs layer is already real and stable:

- `SpecificationSource`
- `SpecificationSourceRecord`
- `Specification`
- `SpecChunk`
- `EmbeddingModel`

This already supports:

- uploading or creating spec sources
- parsing them into reviewable records
- importing selected records into canonical specifications
- chunking and indexing for retrieval
- traceability between requirements and test assets

This is the future RAG grounding layer for AI generation.

### 3.4 Test repository

The repository domain is already structured:

- `TestSuite`
- `TestSection`
- `TestScenario`
- `TestCase`
- `TestCaseRevision`

This is the canonical testing structure.

Important properties:

- scenarios and cases are organized under suites and sections
- test cases hold structured design fields
- revisions preserve immutable snapshots of revision-worthy fields
- linked specifications connect the repository back to requirements

This is one of the strongest pieces of the platform.

### 3.5 Planning and execution records

We already added revision-safe execution planning:

- `TestPlan`
- `TestRun`
- `TestRunCase`

Important rule:

- `TestRunCase` pins both the live `TestCase` and the exact `TestCaseRevision`

This means execution history is tied to the actual case content that existed when the run started.

### 3.6 Automation domain

The automation backend already has the core entities:

- `AutomationScript`
- `TestExecution`
- `TestResult`
- `ExecutionStep`
- `TestArtifact`
- `ExecutionCheckpoint`
- `ExecutionEnvironment`
- `ExecutionSchedule`

This gives us the backend shape needed for:

- storing executable scripts
- triggering runs
- recording step-by-step execution
- storing artifacts and screenshots
- pausing for human checkpoints
- scheduling future runs

### 3.7 Live execution streaming

We built a real live execution telemetry system:

- WebSocket execution stream
- signed stream tickets
- runtime helper event contract
- live step updates
- live artifact publication
- manual checkpoints with resume
- final result and status sync

This gives a non-AI live execution experience:

- watch an execution progress
- see steps and screenshots
- pause for human-required action
- resume and finish

This is important, but it is still telemetry and control, not full remote interactive execution.

### 3.8 Reporting and dashboard backend

We already added reporting read models and endpoints for:

- project overview cards
- recent runs
- pass-rate trends
- failure hotspots

This means the backend can already support real dashboards from stable run and result data.

### 3.9 Integrations foundation

We also laid down normal product integrations:

- `RepositoryBinding`
- `WebhookEvent`
- `ExternalIssueLink`
- `IntegrationActionLog`

This is important for Jira, GitHub, Jenkins, and future external tooling.

## 4. Current frontend state

The frontend already has a real base, but it is still incomplete.

### What exists

- auth and layout shell
- projects page
- project workspace page
- left repository tree
- right repository detail panels
- entity-aware repository read panels
- case editor modal and structured test steps editing
- project members management

### Current strengths

- repository UX has a real shape now
- the current folder architecture is good enough to keep building on:
  - `pages`
  - `components`
  - `api`
  - `types`
  - `router`
  - `store`

### Current gaps

- specs UI is not built yet
- automation UI is not built yet
- run/execution UX is still underexposed
- reporting frontend is not yet surfaced properly
- traceability is still mostly backend-capable but frontend-light

## 5. What the platform can do right now

As of now, the product can already:

- manage org/team/project membership
- ingest and store specifications
- maintain a structured repository of suites, sections, scenarios, and cases
- preserve test case revisions
- link test cases to specifications
- create plans and runs
- expand runs into revision-safe run-cases
- store automation scripts
- execute automation scripts through the current backend execution pipeline
- stream execution events live
- store results, steps, and artifacts
- support human checkpoints
- expose reporting data from run history

That is already a serious non-AI QA platform backbone.

## 6. What the platform does not have yet

These are the biggest missing pieces.

### 6.1 Complete specs UX

The specs backend exists, but the user-facing workflow is still missing:

- source upload and intake UI
- source review UI
- imported specification browser
- traceability-driven spec detail views

### 6.2 Automation execution center

The automation backend exists, but the frontend still needs:

- execution list
- execution detail
- live step timeline
- artifact viewer
- checkpoint controls
- result inspection

### 6.3 Remote interactive browser execution

We do not have a KaneAI-style remote session yet.

Missing later:

- browser session rendered in the UI
- remote takeover
- live session pixels or video
- true remote operator interaction

### 6.4 Distributed execution

We do not yet have:

- container-per-run execution
- VM-per-run execution
- cloud worker pools
- real parallel distributed dispatch

### 6.5 Reviewed AI generation workspace

We do not yet have the future AI layer where a user can give:

- prompt + spec + URL
- prompt + screenshot + spec
- screenshot only

and then receive reviewed, editable generated scenarios and cases.

## 7. Clarification on live streaming vs KaneAI behavior

This matters because expectations must be clean.

### What live streaming currently means in BIAT

The current live streaming system gives:

- live execution status
- step updates
- artifacts appearing during execution
- checkpoints and resume
- final results

### What it does not mean

It does not mean:

- remote browser rendered in the product
- AI agent driving the browser
- containerized browser orchestration
- interactive visual session control inside the UI

So the current automation app is the execution backbone, not the final KaneAI-style experience.

## 8. Long-term AI direction

The future AI direction we want is compatible with the platform.

The desired future experience is something like:

- user gives a prompt
- user adds spec, URL, screenshot, or a mix of them
- system retrieves relevant requirements, older specs, related test assets, and useful memory
- model generates candidate scenarios and cases
- user reviews, edits, accepts, or rejects them
- accepted items become canonical repository records

Later, the flow can extend into automation and execution.

### Important rule

AI must not bypass the platform's canonical models.

That means:

- AI generation should produce reviewed candidates first
- accepted output becomes real `TestScenario` and `TestCase` records
- repository integrity, traceability, and revision safety must stay intact

This means the AI layer does not collide with the platform.
It sits above it.

## 9. Future memory and retrieval layers

When AI generation arrives later, retrieval should not be treated as one vague memory bucket.

We should think in layers:

- requirements memory
  - specs
  - spec chunks
  - source records

- design memory
  - historical scenarios
  - test cases
  - revisions

- execution memory
  - results
  - artifacts
  - failures
  - flaky patterns

- automation memory
  - old scripts
  - execution patterns
  - framework-specific examples

This layered memory model fits the architecture we already built.

## 10. Recommended build order from here

This is the clean next order for the product.

### Phase 1 - Finish repository UX

- tighten the repository workspace
- preserve the current folder architecture
- keep the right panel read-first
- keep case editing structured and clean

### Phase 2 - Build specs workspace

- source intake
- source review
- imported specifications view
- traceability-first detail panels

### Phase 3 - Build automation execution center

- execution list
- live execution detail
- steps, artifacts, checkpoints, results

### Phase 4 - Triggering and operator polish

- easier execution launching
- better result inspection
- stronger frontend around current backend execution features

### Phase 5 - Worker and execution abstraction

- separate local subprocess execution from future remote execution modes
- make execution backends pluggable

### Phase 6 - Parallel and cloud/container execution

- dispatch by `TestRunCase`
- container or VM workers
- cloud/browser-grid style execution
- concurrency control and worker orchestration

### Phase 7 - Reviewed AI generation workspace

- prompt + spec + URL
- prompt + screenshot + spec
- screenshot-only generation
- RAG-grounded scenario and case generation
- human review before commit

### Phase 8 - Remote interactive AI execution

- live remote browser session
- human takeover
- AI-guided or AI-assisted execution behavior
- Kane-style richer execution UX if still desired

## 11. Final product vision

The final product we are moving toward is:

- a strong test management platform first
- with requirements, repository, revisions, runs, automation, and reporting as the stable core
- then a reviewed AI generation layer on top
- then later a richer remote execution and cloud worker layer

In short:

BIAT TestManager should become a serious QA platform with AI-enhanced design and later advanced execution, not a thin AI demo built on weak domain models.

That is the objective behind all of the work done so far.
