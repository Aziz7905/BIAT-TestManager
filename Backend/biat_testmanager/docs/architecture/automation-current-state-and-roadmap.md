# Automation Current State And Roadmap

Last updated: 2026-04-19

This document explains:

1. what the automation app already does
2. what the live streaming work actually gave us
3. why that is not yet KaneAI-style behavior
4. what still needs to be built later

The goal is to keep a clear mental model of the system and avoid mixing up:

- live execution telemetry
- remote browser execution
- cloud/container orchestration
- AI-guided execution

## 1. Short version

What we have now is a strong **execution backbone**:

- revision-safe test execution
- durable run and run-case records
- automation scripts linked to test cases and optionally revisions
- live step and status streaming over WebSocket
- screenshots and artifacts persisted during execution
- manual checkpoint pause/resume support

What we do **not** have yet is the full KaneAI-like experience:

- remote browser session rendered inside the UI
- human takeover of that browser session
- AI agent deciding actions in real time
- isolated cloud workers or containers for each execution
- real parallel distributed execution

So the current system is a good foundation, but it is **not yet a KaneAI clone**.

## 2. What the backend already has

### Repository and execution safety

The test domain is already structured and execution-safe:

- `TestCase` is the live design record
- `TestCaseRevision` is the frozen design snapshot
- `TestPlan` groups execution intent
- `TestRun` is a run instance
- `TestRunCase` is the execution unit inside a run
- `TestRunCase` pins the exact case revision used at execution time

This matters because future workers, retries, and parallel dispatch need a stable execution target.

### Automation domain

The automation app already has:

- `AutomationScript`
- `TestExecution`
- `TestResult`
- `ExecutionStep`
- `TestArtifact`
- `ExecutionCheckpoint`
- `ExecutionEnvironment`
- `ExecutionSchedule`

This means the backend can already represent:

- what script ran
- against what case and revision
- under what environment
- what happened step by step
- what artifacts were produced
- whether manual intervention was needed

## 3. What the live streaming work actually built

The live streaming work was not a browser-streaming system. It was a **live execution event pipeline**.

### Current execution flow

At a high level:

1. A `TestExecution` is created and queued.
2. The worker selects the linked automation script.
3. For Python automation scripts, the backend writes the script to a temporary file.
4. The worker launches that script as a subprocess on the machine running the execution worker.
5. The script can emit BIAT runtime events such as:
   - step started
   - step passed
   - step failed
   - artifact created
   - checkpoint requested
6. The backend converts those runtime events into durable records:
   - `ExecutionStep`
   - `TestArtifact`
   - `ExecutionCheckpoint`
7. The backend publishes those updates over WebSocket to the frontend.
8. The final outcome is persisted in `TestResult`.
9. Run-case status is synchronized back to the test run layer.

### Runtime helper contract

The runtime helper currently supports event emission through a reserved prefix:

- `__BIAT_EVENT__<json>`

The helper functions include:

- `report_step_started(...)`
- `report_step_passed(...)`
- `report_step_failed(...)`
- `artifact_created(...)`
- `require_human_action(...)`

This is what allows the backend to stream execution progress live.

### Checkpoint support

The system also supports a non-AI checkpoint flow:

- execution pauses when a script requests human action
- a checkpoint record is created
- the frontend can later resume the checkpoint through the API
- the worker sees a resume control signal and continues

This gives a real human-in-the-loop execution path, but it is still not remote browser control.

## 4. What the current live streaming gives the product

Today the automation backend can power a UI like:

- click an execution
- watch status updates arrive live
- see steps move from pending to running to passed or failed
- see screenshots and artifacts appear
- see a checkpoint pause the run
- resume the checkpoint
- see the final pass/fail result

This is valuable and real.

It gives:

- execution observability
- operator awareness
- durable execution history
- manual intervention hooks

But it gives those through **telemetry and control events**, not through a remote visual browser session.

## 5. Why this is not yet KaneAI behavior

KaneAI-style behavior usually implies much more than live status events.

The screenshot-style expectation usually combines four layers:

1. **Execution telemetry layer**
   - steps
   - pass/fail
   - artifacts
   - checkpoints

2. **Remote browser/session layer**
   - the UI shows a live browser session
   - pixels are streamed back to the user

3. **Interactive control layer**
   - the user can take over or interact directly
   - not only resume a checkpoint, but actually operate the browser session

4. **AI/agent layer**
   - the system plans or authors steps
   - the system may decide actions dynamically
   - the UI may group actions into higher-level intent blocks

Right now BIAT has mostly layer 1 and part of layer 3.

It does **not** yet have:

- live remote browser rendering inside the UI
- browser takeover
- VM/container-per-session isolation
- AI decision-making during execution
- Kane-style nested authoring and agent review UX

## 6. What we really built so far

The most accurate description is:

We built the **execution backbone and event streaming foundation** for future richer automation UX.

That includes:

- revision-safe run execution
- worker-friendly run-case model
- event-driven step persistence
- artifact persistence
- manual checkpoints
- WebSocket updates
- execution environment abstraction

This is the right backend groundwork for later:

- local execution
- container execution
- VM execution
- cloud execution
- parallel workers
- remote session streaming
- AI execution flows

## 7. What is still missing

### A. Remote session layer

To feel like KaneAI, BIAT still needs a real remote session layer.

That could be implemented later through one of these approaches:

- browser running in a container + noVNC
- browser running in a VM + streamed desktop
- Playwright/CDP-backed remote session viewer
- WebRTC-based live browser/video streaming

Without this, the user only sees telemetry, not the live browser itself.

### B. Execution isolation layer

Today execution is fundamentally local-worker oriented.

Future work should allow a worker to execute in:

- local process
- Docker container
- remote VM
- Selenium Grid or browser farm
- cloud worker

This is where `ExecutionEnvironment` becomes more important later.

### C. Parallel dispatch layer

The domain already supports the right execution unit:

- `TestRunCase`

That means parallel execution later should dispatch **run-cases**, not whole runs.

Still missing later:

- worker queue policy
- worker claiming and lease renewal strategy
- concurrency limits
- container or VM spawning per run-case
- retry policy and backoff rules

### D. AI execution and authoring layer

For real KaneAI-style behavior, BIAT would later need:

- AI-generated test steps or grouped intent blocks
- AI-generated automation scripts from structured test cases
- agent-assisted execution or recovery logic
- reviewed AI output instead of blind automation

That layer should be built on top of the stable non-AI records, not replace them.

## 8. Why the current work still matters

Even though it is not yet KaneAI behavior, the current work is not wasted.

It already gives us the hard non-AI backbone needed before any serious AI or cloud execution layer:

- a proper run model
- revision pinning
- execution status tracking
- live event transport
- step persistence
- checkpoint handling
- artifact history

If we had skipped this and jumped straight to a flashy browser UI, the architecture would be much weaker.

## 9. Recommended future order

The clean future path is:

1. **Frontend automation execution center**
   - expose what already exists
   - execution list, detail, steps, checkpoints, results, artifacts

2. **Execution triggering polish**
   - make it easier to launch and inspect executions from the product

3. **Execution worker abstraction**
   - separate local subprocess execution from future container/VM execution

4. **Parallel dispatch by `TestRunCase`**
   - allow multiple workers to pick up run-cases

5. **Remote browser/session streaming**
   - render the live browser session inside the UI

6. **Cloud/container execution**
   - worker pools, isolated browser sessions, remote environments

7. **AI-assisted authoring and execution**
   - Kane-style generation, grouping, guidance, or agent flows

## 10. Final mental model

Use this distinction:

- **What BIAT has now:** live execution telemetry and control foundation
- **What KaneAI-like UX needs later:** remote session infrastructure plus optional AI orchestration

So if the question is:

“Did we already build KaneAI behavior?”

The honest answer is:

**No.**

We built the backend execution foundation that can later support part of that experience.

That is the right direction, but it is only the foundation stage.
