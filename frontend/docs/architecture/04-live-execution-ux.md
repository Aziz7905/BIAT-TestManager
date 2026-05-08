# 04 — Live Execution UX

**Stream policy in the UI. Debug rerun. noVNC viewer. Full-screen mode. Checkpoint modals.**

---

## 1. The streaming policy in the UI

The backend streams events via WebSocket and browser pixels via noVNC. The frontend's job is to **respect the opt-in policy** — don't open streams the user didn't ask for.

### 1.1 The two streams
| Stream | Purpose | Frontend action |
|---|---|---|
| **Event stream** (`ws/executions/<id>/?ticket=...`) | Status, step, artifact, checkpoint events | Open by default for any execution detail view |
| **Browser pixel stream** (`ws/executions/<id>/browser/`) | Live noVNC pixels | Open only when execution has `stream_enabled=True` |

Event streams are cheap and informative. Pixel streams are heavy and only useful when a human is actively watching.

### 1.2 Decision matrix in the UI
| User action | Event stream | Pixel stream |
|---|---|---|
| Opens a regular regression execution detail page | Yes | No (off by default) |
| Clicks "Watch this run" before triggering | Yes | Yes (sets `stream_enabled=True` on creation) |
| Clicks "Debug Rerun" on a failed test | Yes | Yes (creates new execution with `stream_enabled=True`) |
| Opens an AI agent session live view | Yes | Yes (always-on for agent sessions) |
| Opens a manual diagnostic browser session | Yes | Yes (always-on) |
| Looks at a completed (terminal) execution | No (final state already loaded) | No (use the recorded video instead) |

---

## 2. The two viewing surfaces

### 2.1 Inline workspace view
Inside `Automation` tab → `ProjectAutomationWorkspace`.
- Sidebar: list of recent executions
- Main area: browser panel + step timeline + result panel
- noVNC sized to fit the panel
- Default view for users staying in their project workspace

### 2.2 Full-screen view (`AutomationLivePage`)
Route: `/projects/:id/automation/executions/:executionId/live`
- Browser panel takes most of the screen
- Step timeline as a side rail
- "Exit full screen" button → back to workspace

Both surfaces share the same `executionStore` and the same WebSocket connection. The difference is layout, not data.

---

## 3. The `executionStore` and event merging

```typescript
// store/executionStore.ts (simplified shape)
type ExecutionStore = {
  execution: TestExecution | null;
  steps: ExecutionStep[];
  artifacts: TestArtifact[];
  checkpoints: ExecutionCheckpoint[];
  result: TestResult | null;
  isStreamConnected: boolean;

  loadInitialSnapshot: (executionId: string) => Promise<void>;
  connectStream: (executionId: string, ticket: string) => void;
  disconnectStream: () => void;
  applyEvent: (event: WsEvent) => void;
};
```

### 3.1 The merge logic
```typescript
applyEvent(event) {
  switch (event.type) {
    case 'status_changed':
      execution.status = event.status;
      execution.started_at ??= event.started_at;
      execution.ended_at = event.ended_at;
      break;

    case 'step_event':
      // Upsert by step_index
      const idx = steps.findIndex(s => s.step_index === event.step.step_index);
      if (idx >= 0) steps[idx] = event.step;
      else steps.push(event.step);
      break;

    case 'artifact_event':
      artifacts.push(event.artifact);
      break;

    case 'checkpoint_event':
      // Upsert checkpoint, drive modal
      ...

    case 'result_event':
      result = event.result;
      break;
  }
}
```

Components subscribe to slices (steps, status, etc.) using Zustand's selector pattern to avoid full-tree re-renders.

---

## 4. The noVNC viewer

### 4.1 Component: `NoVncViewer`
```tsx
<NoVncViewer
  executionId={execution.id}
  scaleViewport={true}
  onConnect={() => ...}
  onDisconnect={() => ...}
/>
```

Uses the `noVNC` RFB library directly:
1. Open WebSocket to `ws/executions/<id>/browser/` (auth-checked by backend)
2. Pass to `RFB`'s constructor
3. RFB handles the VNC handshake and pixel rendering

### 4.2 Sizing
`scaleViewport=true` lets RFB scale the canvas to fit the panel. There's a quirk: layout sometimes settles late, so we fire a `resize` event ~1s after RFB connects to force a rescale.

```tsx
useEffect(() => {
  if (rfb && connected) {
    const timer = setTimeout(() => {
      window.dispatchEvent(new Event('resize'));
    }, 1000);
    return () => clearTimeout(timer);
  }
}, [rfb, connected]);
```

### 4.3 Why no iframe fallback
The original implementation had an iframe path as a fallback. It was removed because:
- Iframes can't proxy auth properly through the Channels consumer
- The two paths diverged in features (no scroll/zoom in iframe)
- Maintaining two viewer paths doubled the bug surface

If RFB fails (e.g., the noVNC consumer is down), show an explicit error: "Live browser stream unavailable. Try again or use the recorded video."

### 4.4 Bidirectional input
RFB supports keyboard and mouse input from the user back to the browser session — useful for **manual diagnostic sessions** where the user is actively interacting with the app, not just watching.

For automated executions, input is irrelevant (the script is driving). For agent sessions, input lets the user **take over** the agent's browser — Phase E feature.

---

## 5. Step timeline

A scrollable list of `ExecutionStep` rows:

```
┌──────────────────────────────────────────────┐
│  ✓ Step 1   open URL                  1.2s  │
│             https://app.bank.local/login    │
│  ✓ Step 2   enter username            0.3s  │
│             "ahmed"                          │
│  ✓ Step 3   enter password            0.2s  │
│             "•••••••"                        │
│  ⟳ Step 4   click submit              ...   │
│             #login-submit                    │
│  ⏸ Step 5   verify dashboard         pending │
└──────────────────────────────────────────────┘
```

- Status icons: ✓ passed, ✗ failed, ⟳ running, ⏸ pending, ⏱ timeout
- Click a step to expand: full action details, screenshot if any, error message if failed
- Auto-scroll to the most recent running step
- The user can pause auto-scroll by manually scrolling up

---

## 6. Result panel

When `TestResult` arrives:
```
┌──────────────────────────────────────────────┐
│  RESULT: PASSED ✓                            │
│  Duration: 12.4s                              │
│  Steps: 5/5 passed                            │
│                                              │
│  Artifacts:                                   │
│  📷 Final screenshot → [View] [Download]    │
│  🎥 Full session video → [View] [Download]  │
│  📄 JUnit XML → [Download]                  │
│                                              │
│  RCA (AI): "..."                              │
│                                              │
│  [Re-run] [Debug Rerun]                       │
└──────────────────────────────────────────────┘
```

For failed runs: error message prominent at top, RCA below (Phase D), screenshot of the failure point shown.

Artifacts use pre-signed MinIO URLs — clicking opens or downloads directly from MinIO, not through Django.

---

## 7. Checkpoint modal (human-in-the-loop)

When a `checkpoint_event` arrives with `status='pending'`:

```
┌──────────────────────────────────────────────┐
│  HUMAN ACTION REQUIRED                       │
│                                              │
│  Title: MFA Verification                     │
│  Instructions:                                │
│    Please complete the MFA challenge in the   │
│    browser and click Resume when done.        │
│                                              │
│  Step: 7 — verify mfa code                   │
│                                              │
│  [Cancel Execution]    [Resume]              │
└──────────────────────────────────────────────┘
```

The modal:
- Auto-opens when the event arrives
- Stays open until the user clicks Resume or Cancel
- Resume → `POST /api/test-executions/<id>/checkpoints/<cid>/resume/` with optional payload
- Cancel → marks the execution as cancelled

The user typically interacts with the noVNC stream beneath/beside the modal — completing the MFA in the live browser, then clicking Resume.

---

## 8. Debug rerun

The "Debug Rerun" button on a failed `TestExecution`:

```
1. User clicks Debug Rerun
       ↓
2. Frontend: POST /api/test-executions/<id>/debug-rerun/
       ↓
3. Backend: creates a new TestExecution with:
   - same script, environment
   - debug_rerun = True
   - stream_enabled = True
   - trigger_type = 'manual'
       ↓
4. Backend returns the new execution id
       ↓
5. Frontend: navigates to the new execution's detail
       ↓
6. Auto-opens noVNC viewer (stream_enabled=True)
       ↓
7. User watches what happens this time
```

Visual differentiator: debug runs get a "Debug" badge in the timeline so the user knows which attempt is which.

---

## 9. Triggering a run

```
User clicks "Run" on a TestRunCase or a whole TestRun
       ↓
"Run" dialog opens:
   ┌───────────────────────────────────────┐
   │  Run options                          │
   │  Browser: [Chrome ▼]                  │
   │  Environment: [Production ▼]          │
   │  ☐ Watch this run live                │
   │           [Cancel] [Run]              │
   └───────────────────────────────────────┘
       ↓
On Run:
  if "Watch this run live" checked:
    POST /api/.../execute/ with stream_enabled=true
    On response, navigate to the execution detail and open noVNC
  else:
    POST /api/.../execute/ with stream_enabled=false
    Show a toast "Execution queued — view results in Test Runs"
```

The "Watch this run live" checkbox is the explicit opt-in for streaming. Default unchecked.

---

## 10. Why no auto-open noVNC

Tempting to think "open the noVNC every time" — it feels like a richer UX. We don't because:

- 1000 silent regression runs at scale → 1000 noVNC connections is unsustainable
- Most regression runs happen overnight or in CI — no human is watching
- A user who navigates to an execution detail isn't necessarily there to watch live; they may just want to read the result
- The recorded video preserves the same information for later viewing

The opt-in policy keeps the platform usable at scale and the architecture honest.

---

## 11. Performance considerations

### 11.1 The step timeline can grow
Long-running executions (1000+ steps) make the timeline expensive to render. Use:
- React's `key` prop on each step (`key={step.id}`)
- `React.memo` on the step row component
- Virtualization (e.g., `react-window`) when count exceeds 200

The current implementation handles up to ~500 steps without virtualization; add it when real executions push past that.

### 11.2 WebSocket reconnect
If the WebSocket drops:
- Retry with exponential backoff up to N attempts
- On reconnect, fetch the current snapshot to catch up on missed events
- Show a "Reconnecting..." banner during retries

### 11.3 Don't double-subscribe
A user navigating between executions shouldn't end up with two open WebSocket connections. The `executionStore.connectStream()` always disconnects any existing stream first.

---

## 12. The full-screen page (`AutomationLivePage`)

```
┌──────────────────────────────────────────────────────────────┐
│  ← Back to project                            Exec #4523    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│                                              │  TIMELINE     │
│                                              │  ✓ Step 1     │
│            [browser pixels — noVNC]          │  ✓ Step 2     │
│                                              │  ⟳ Step 3     │
│                                              │  ⏸ Step 4     │
│                                              │               │
│                                              │  RESULT       │
│                                              │  (pending)    │
│                                              │               │
└──────────────────────────────────────────────────────────────┘
```

Same data as the inline view, different layout. Used for:
- Demos / presentations (full-screen looks better)
- Debug reruns (more browser real estate)
- AI agent sessions (more room to watch the agent)

The "Full screen" button on the inline view opens this in the same tab. The user can navigate back via browser back or the explicit link.
