# Phase 4 Analysis & Next Steps

## Current State

You've successfully implemented Phase 4: Selenium Grid + browser streaming. The architecture now has:

- **Backend**: Manual browser sessions (diagnostic), Selenium Grid integration via RemoteWebDriver, VNC streaming via WebSocket proxies, real-time execution events via Django Channels
- **Frontend**: noVNC RFB viewer (direct WebSocket), iframe fallback (noVNC pages), full-screen live execution page, execution step streamer
- **Live Execution State**: Zustand store merges snapshot + event stream → real-time execution + steps + artifacts + checkpoints

### What Works
- Selenium Grid + VNC display (1920x1080) with 3 Chrome nodes
- Test cases can open a browser via "Open browser" button → creates manual execution
- Browser streams live to noVNC viewer during execution
- Step events arrive live, execution status updates in real-time
- "Live view" button opens dedicated full-screen page for live execution

### Known Issues (User-Reported)

1. **3 Overlapping Streaming Views** — User sees 3 different ways to view a live browser stream, wants to eliminate the redundant one
2. **Browser Image Size During Streaming** — Browser doesn't fill the panel properly, appears small/wrong dimensions
3. **Test Runs Page Useless** — "blended and kinda useless", disconnected from actual execution results, shows only manual status dropdowns

---

## Issue 1: 3 Overlapping Streaming Views

### Current Implementation

You have **3 browser streaming surfaces**:

1. **NoVncViewer in ProjectAutomationWorkspace** (main workspace)
   - Appears in the browser panel when you select an execution in the sidebar
   - Shows steps on left, browser on right, results below
   - File: [ProjectAutomationWorkspace.tsx:388-396](../../frontend/src/components/project/automation/ProjectAutomationWorkspace.tsx#L388-L396)
   - Only visible when `has_browser_session === true` AND status is `running`/`paused`

2. **NoVncViewer in AutomationLivePage** (dedicated full-screen live view)
   - Accessed via "Live view" link at [ProjectAutomationWorkspace.tsx:341-346](../../frontend/src/components/project/automation/ProjectAutomationWorkspace.tsx#L341-L346)
   - Opens `/projects/{id}/automation/executions/{executionId}/live` route
   - File: [AutomationLivePage.tsx:265-270](../../frontend/src/pages/AutomationLivePage.tsx#L265-L270)
   - Full-screen layout: steps sidebar on left, browser filling right side
   - Used when user clicks "Live view" button or when workflow sends `focusExecutionId` prop (which activates `compactAutomationHeader` and hides bottom panel)

3. **Iframe Fallback in NoVncViewer** (redundant fallback)
   - Appears when RFB WebSocket fails to connect, falls back to iframe showing noVNC pages
   - File: [NoVncViewer.tsx:231-235](../../frontend/src/components/project/automation/NoVncViewer.tsx#L231-L235)
   - Shows browser URLs as clickable iframes
   - User says: "this shows after i press run inside the test case" — appears as 3rd view in the case workspace

### The User's Intent

User wants to eliminate the **iframe fallback view** because:
- RFB direct WebSocket is the primary/best way to stream
- If RFB fails, it's better to show an error or "stream unavailable" message
- The iframe fallback is redundant when you already have:
  - Main workspace view (NoVncViewer RFB)
  - Full-screen live page (AutomationLivePage with NoVncViewer)

### Solution Direction

**Remove the iframe fallback entirely** from NoVncViewer:
- Delete the `{enabled && browserViewUrls.length > 0 && ...}` section (lines 210-237)
- Keep only the RFB viewer (canvas mode) and the empty "No Session" state
- If RFB fails, show error message instead of iframe fallback
- Simplifies the viewer and removes redundant view

---

## Issue 2: Browser Image Size During Streaming

### Current Behavior

User reports: "the image isn't taking the right size while streaming the live browser"

From earlier context, you fixed the Chrome window size issue:
- Changed from `--window-size=1280,900` to `--start-maximized` → Chrome now fills 1920x1080 VNC display
- Added `globalThis.dispatchEvent(new Event("resize"))` in NoVncViewer after RFB connection to force scaling recalculation

### Current Implementation

NoVncViewer:
- Container: `className="relative min-h-0 min-w-0 flex-1 overflow-hidden bg-slate-950"`
- RFB target: `<div ref={containerRef} className="absolute inset-0" />` (fills container)
- RFB initialized with: `rfb.scaleViewport = true` (scales display to fit container)

BrowserCanvas (loading state):
- Same container structure, shows spinner while loading

### Why It Might Still Be Too Small

**Hypothesis**: The panel itself might not be filling available space properly:

1. **In ProjectAutomationWorkspace** (line 377):
   - Browser panel: `<div className="flex min-w-0 flex-1 overflow-hidden">`
   - This should fill remaining space, but depends on parent flex layout
   - Parent: `<div className="flex min-h-0 flex-1 overflow-hidden">` (line 352)
   - Parent container is `<div className="flex flex-1 flex-col overflow-hidden">` (line 290)
   - All should work correctly with flex layout

2. **In AutomationLivePage** (line 264):
   - Browser section: `<section className="min-w-0 flex-1 overflow-hidden bg-slate-950">`
   - Parent: `<main className="flex min-h-0 flex-1 overflow-hidden">` (line 224)
   - Parent: `<div className="flex h-screen flex-col overflow-hidden bg-white">` (line 170)
   - Should work correctly

**Possible issues**:
- RFB scaleViewport behavior — might be scaling to a smaller size than available space
- RFB viewOnly mode interaction with scaling
- Steps panel in ProjectAutomationWorkspace taking up too much space (currently `w-[280px] xl:w-[300px]`)

### Solution Direction

**Verify and potentially adjust**:
1. Ensure the RFB container reaches full available size (might need React DevTools inspector)
2. If needed, add explicit size constraints or test scaleViewport=false to see if that's the issue
3. Consider making the steps panel collapsible/hideable to maximize browser view space

---

## Issue 3: Test Runs Page Disconnected from Execution Results

### Current Implementation

**Backend Endpoint**: `GET /api/test-runs/{run_pk}/cases/`
- File: [runs.py:163-169](../../Backend/biat_testmanager/src/apps/testing/views/runs.py#L163-L169)
- Returns TestRunCase with:
  - run.name, test_case.title, test_case_revision.version_number
  - assigned_to, status (manual enum)
  - created_at, updated_at
- **Missing**: No link to actual TestExecution results

**Frontend Workspace**: [ProjectTestRunsWorkspace.tsx](../../frontend/src/components/project/test-runs/ProjectTestRunsWorkspace.tsx)
- 3-pane layout: Plans | Runs | Run Cases
- Loads plans, runs, run cases
- For each run case, shows: title, revision, status (dropdown), assignment
- **No integration with execution results**

### Data Model Relationship

```
TestCase → (has many) TestExecution  [one execution per run]
           ↓
        TestRunCase [one per test plan run, manual status]
           ↓
        [Manual status dropdown: pending/running/passed/failed/skipped/error/cancelled]
```

**Key Issue**: TestRunCase.status is **manually assigned**, separate from TestExecution results. This is intentional (for manual testing), but the backend doesn't expose which TestExecution corresponds to which TestRunCase.

### Why It's Useless Now

1. **No Execution Context** — Can't see what actually happened when a test ran
2. **No Results** — No pass/fail details, errors, screenshots, timing
3. **No History** — Can't compare multiple runs of the same case
4. **Incomplete Data** — Passes back only what's manually entered, not actual test results

### Legitimate Use Case

A QA team wants to:
1. Create a test plan with 20 test cases
2. Run the plan (start_test_run)
3. For each case, see:
   - **If automated** (has AutomationScript): Show TestExecution results (passed/failed + details)
   - **If manual** (no script): Allow manual status entry via dropdown
4. View overall run summary: pass rate, which cases failed, timing, artifacts

### Solution Direction

**Connect TestRunCase to TestExecution**:
1. Add `execution_id` foreign key to TestRunCase (links to latest/specific execution)
2. Create endpoint that returns TestRunCase with nested execution data (if exists)
3. Update frontend to show execution results when available
4. Keep manual status dropdown for non-automated cases or post-execution override

---

## Suggested Implementation Order

### Phase 4.1: Clean Up Browser Streaming (This Session)
1. **Remove iframe fallback** from NoVncViewer (eliminates redundant view #3)
2. **Verify browser sizing** is working correctly in both workspace and live page
3. **Test** the fixes with a live execution

### Phase 4.2: Connect Test Runs to Execution Results (Follow-up)
1. **Audit data flow**: Understand how TestRunCase relates to TestExecution now
2. **Add execution link**: Either add `execution_id` FK or query latest execution for case + run
3. **Update serializer**: Include execution results in TestRunCase response
4. **Update frontend**: Show execution data when available, manual dropdown as fallback

---

## Codebase Context

**Key Files Modified in Phase 4**:

Backend:
- `automation/runtime.py` — BIAT runtime helpers (create_driver, report_session_started, etc.)
- `automation/services/manual_browser.py` — Diagnostic browser sessions, Grid driver creation
- `automation/services/grid.py` — Maps session_id to VNC URLs via Grid API
- `automation/services/streaming.py` — WebSocket path generation (RFB + iframe fallback URLs)
- `automation/consumers.py` — WebSocket consumers for execution stream + browser stream proxy
- `testing/services/runs.py` — Test run/case creation and expansion
- `testing/serializers/runs.py` — Run/case serialization
- `testing/views/runs.py` — REST endpoints

Frontend:
- `components/project/automation/NoVncViewer.tsx` — RFB viewer + iframe fallback + scaling logic
- `components/project/automation/ProjectAutomationWorkspace.tsx` — Main automation dashboard
- `pages/AutomationLivePage.tsx` — Dedicated full-screen live execution view
- `store/executionStore.ts` — Zustand store for live stream + events
- `api/runs.ts` — Test run/case API calls
- `components/project/test-runs/ProjectTestRunsWorkspace.tsx` — Test runs page (disconnected from execution results)

**Memory References**:
- **Project Roadmap**: Phase A (current) = Selenium Grid execution ✓ now complete, Phase B = Parallel execution UI (multi-stream viewing), Phase C = Reporting, Phase D = AI test generation
- **User Profile**: Non-AI core must be solid first, prefers honest answers, wants surgical changes only

---

## Summary

**Immediate fixes** (Phase 4.1):
1. Remove iframe fallback view from NoVncViewer
2. Verify browser image sizing in both workspace and live page
3. Test with live execution to confirm both views work correctly

**Follow-up work** (Phase 4.2):
1. Analyze TestRunCase ↔ TestExecution relationship
2. Connect run cases to execution results
3. Update frontend to show real execution data instead of just manual status dropdowns

---

## Questions Before Implementation

1. **Browser sizing**: Should we verify with screenshots before removing iframe fallback? Or is the max-size issue already solved and just needs iframe removed?
2. **Test Runs use case**: Should TestRunCase always link to exactly one TestExecution? Or can multiple executions happen for the same run case (retries)?
3. **Phase ordering**: Do you want to fix browser streaming first, then come back to Test Runs? Or tackle both simultaneously?
