# 06 — Storage and Streaming

**MinIO for artifacts. The streaming policy (when to stream, when to stay silent). Debug rerun mode. Video recording strategy.**

---

## 1. Why we don't store artifacts on the filesystem

Previously, artifacts pointed to a local directory on the worker host. Three problems:

1. **Server bloat** — at scale (10,000 executions, each with screenshots/videos), this fills disk quickly and silently
2. **Container incompatibility** — when execution moves to a runner container (see [`05-execution-engine.md`](05-execution-engine.md)), the runner's filesystem is ephemeral. A shared volume works but is fragile
3. **No backup story** — local disk has no built-in versioning, replication, or retention policy

The fix: object storage.

---

## 2. The storage choice: MinIO

### 2.1 Options considered

| Option | Verdict |
|---|---|
| **AWS S3** | Reject — data leaves the bank's network, regulatory non-starter |
| **Azure Blob Storage** | Reject — same as S3, plus BIAT isn't on Azure |
| **Google Cloud Storage** | Reject — same |
| **MinIO** | **Accept** — self-hosted, S3-compatible, runs as a Docker container, data stays on-premise |
| **Local filesystem (today)** | Reject for the reasons above |

### 2.2 Why MinIO is the right fit
- **S3-compatible API** — use `boto3` exactly as you would with real S3. Future migration to actual S3 is a one-line endpoint change
- **Self-hosted** — runs as `docker run minio/minio server /data` next to the rest of the stack
- **No data leaves the network** — required for a bank
- **Free** — no per-GB pricing
- **Pre-signed URLs** — frontend downloads directly from MinIO without proxying through Django

### 2.3 The MinIO topology
```
┌─────────────────────────────────────────────┐
│          BIAT TestManager Server            │
│                                             │
│  ┌────────────┐   ┌──────────────────┐      │
│  │  Django    │   │  Celery worker   │      │
│  │            │   │                  │      │
│  └─────┬──────┘   └─────┬────────────┘      │
│        │                │                   │
│        └────┬───────────┘                   │
│             ▼                               │
│      ┌──────────────────┐                   │
│      │   MinIO          │                   │
│      │   (container)    │                   │
│      │   :9000 — API    │                   │
│      │   :9001 — admin  │                   │
│      └──────────────────┘                   │
│                                             │
│  Bucket: biat-artifacts                     │
└─────────────────────────────────────────────┘
```

---

## 3. Bucket layout and key naming

### 3.1 Single bucket, project-scoped key prefixes
```
biat-artifacts/
  projects/
    <project-id>/
      executions/
        <execution-id>/
          screenshots/
            step-001.png
            step-007.png
          videos/
            full-run.mp4
          logs/
            stdout.log
          dom-snapshots/
            failure.html
          har/
            network.har
```

### 3.2 Why one bucket, not one-bucket-per-project
- MinIO handles many objects per bucket cleanly
- IAM/access control happens in Django's pre-signed URL generation, not at the bucket level
- Easier backup and lifecycle policies

### 3.3 Lifecycle policies (planned)
- Screenshots from executions older than **90 days**: deleted
- Videos from executions older than **30 days** (unless tagged `keep`): deleted
- Failure-related artifacts: kept indefinitely (or until execution is deleted)

These run as MinIO lifecycle rules, not Celery tasks. The platform doesn't have to think about cleanup.

---

## 4. The `TestArtifact` model migration

### 4.1 Current shape
```python
class TestArtifact(models.Model):
    execution = models.ForeignKey(...)
    artifact_type = models.CharField(...)  # screenshot/video/log/...
    storage_backend = models.CharField(
        max_length=20,
        choices=[("minio", "MinIO"), ("local", "Local")],
        default="minio",
    )
    storage_key = models.CharField(max_length=1024)  # S3/MinIO object key
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

Migration history may still mention the old local field so existing databases can migrate safely, but runtime code uses `storage_backend` and `storage_key`.

---

## 5. The artifact upload flow

### 5.1 From a Docker runner container

```
Runner container produces artifact
   ↓
biat_event_helper.artifact_created(local_path, ...)
   ↓
Helper uses boto3 to PUT the file to MinIO
   ↓
Helper emits __BIAT_EVENT__ with the storage_key
   ↓
Worker reads the event, creates TestArtifact row with the key
   ↓
Container exits, file inside container vanishes (no cleanup needed)
```

The runner container has direct access to MinIO over the Docker network. Credentials are passed in via env vars.

### 5.2 From the worker (for some artifacts produced outside the script)

```
Worker captures something (e.g., final video from Selenoid recording)
   ↓
Worker uploads to MinIO via boto3
   ↓
Worker creates TestArtifact row with the key
```

### 5.3 Frontend access
```
User clicks an artifact in the UI
   ↓
Frontend reads `download_url` from the result/stream artifact payload
   ↓
Backend checks user has project access to the parent execution
   ↓
Backend generates pre-signed MinIO URL (TTL ~5 min)
   ↓
Frontend redirects browser to the pre-signed URL
   ↓
Browser downloads from MinIO directly (Django not in the path)
```

This keeps Django's request/response footprint small even when artifacts are large.

---

## 6. Live streaming — the policy

The streaming subsystem is built. The question is **when to use it.**

### 6.1 The principle
Nobody watches 1000 silent regression tests run live. The default is no stream. Streams open only when a human is **actively watching** — which is most of the time false.

### 6.2 The decision matrix

| Scenario | Stream? | Why |
|---|---|---|
| Layer 3 AI agent session | **Yes (always)** | The whole product experience is watching the agent |
| Debug rerun of a failed test | **Yes (always)** | The user explicitly clicked to investigate |
| Manual diagnostic browser session | **Yes (always)** | The user is operating the browser |
| Layer 2 regression run, "Watch this run" clicked | Yes | Explicit user opt-in |
| Layer 2 regression run, default | **No** | Silent execution |
| Scheduled / CI-CD triggered run | **No** | No human is sitting there |
| Manual test execution (Layer 1, no browser) | N/A | No browser exists |

### 6.3 Implementation: `stream_enabled` field

Add a field to `TestExecution`:
```python
stream_enabled = models.BooleanField(default=False)
```

Set `True` when:
- Layer 3 creates the execution (always)
- The user clicks "Watch this run" before triggering
- The user triggers a "Debug Rerun" of a failed execution
- The execution is for a manual browser session (always)

The WebSocket consumer checks `stream_enabled` before accepting connections to the noVNC stream:
```python
if not execution.stream_enabled:
    raise PermissionDenied("This execution did not enable streaming.")
```

### 6.4 What still streams even when noVNC doesn't

The **event stream** (`ws/executions/<id>/?ticket=...`) — status changes, step updates, artifact events — can still be opened. It's cheap (just JSON over the channel layer) and useful for live monitoring of progress without watching pixels.

So the rule is two streams:
- **Event stream** — useful even for silent runs (live progress dashboard)
- **Pixel stream (noVNC)** — only when watching is the point

---

## 7. The "debug rerun" mode

### 7.1 Use case
A regression run completed. 47 of 50 tests passed. 3 failed. The user wants to investigate **one specific failure**.

### 7.2 The flow
```
1. User views the run results
2. User clicks on a failed TestRunCase
3. User clicks "Debug Rerun" button
4. Backend creates a NEW TestExecution with:
     - same script, same environment
     - trigger_type = "manual"
     - debug_rerun = True   (new field)
     - stream_enabled = True
5. Execution runs on the `interactive` queue, because a human is actively debugging
6. Because stream_enabled=True, noVNC stream auto-opens for the user
7. The user watches what happens — sees the failure live
8. New result recorded under the same TestRunCase as a new attempt
```

### 7.3 Why this is its own mode
- Without it, users would either watch every regression run live (unsustainable) or have no way to investigate failures interactively
- It's a deliberate "give me back interactivity for this one test" affordance
- It naturally creates a new attempt on the same `TestRunCase` (preserves history)

### 7.4 Field on `TestExecution`
```python
debug_rerun = models.BooleanField(default=False)
```

Set this from the API endpoint that triggers a rerun. It enables stream and tags the execution for the UI to show a "Debug" badge.

---

## 8. Video recording

### 8.1 Selenoid video per session
Selenoid supports recording for browser sessions. Each session can produce an MP4 that is uploaded to MinIO and linked to the execution.

### 8.2 Capture flow
```
Session starts → Selenoid begins recording
       ↓
Session ends → Selenoid finalizes the MP4
       ↓
Worker: collect the MP4 from Selenoid
       ↓
Worker: upload to MinIO with key projects/<id>/executions/<eid>/videos/full-run.mp4
       ↓
Worker: create TestArtifact(artifact_type='video', storage_key=key)
```

### 8.3 When videos are kept
- Failed runs: keep the video (useful for debugging)
- Passed runs: keep for 30 days, then auto-delete via MinIO lifecycle
- Debug reruns: keep indefinitely (it's evidence)
- Agent sessions: keep indefinitely (it's the agent's audit trail)

### 8.4 Why video matters
For Layer 2 (regression), video is the **replay-without-live-stream** affordance. A test failed at 3am? You don't need to have watched it live — the video is in MinIO, indexed by execution id. Click, watch, debug.

This is why the streaming policy can be "off by default" — losing the live view is fine because the video preserves the same information.

---

## 9. Storage size estimates

Rough sizing for capacity planning:

| Asset | Typical size | Per execution |
|---|---|---|
| Screenshot (1920×1080 PNG) | 200–500 KB | 5–20 of them |
| Video (1080p, 5 min, MP4) | 50–150 MB | 1 |
| DOM snapshot HTML | 50–500 KB | 0–5 |
| Log file (stdout/stderr) | 10–100 KB | 1 |
| HAR file | 1–5 MB | 0–1 |

**Average execution: ~100 MB.** Bank-scale: 100 executions/day × 100 MB = 10 GB/day = 3.5 TB/year (without lifecycle deletion).

With lifecycle policy (videos: 30 days, screenshots: 90 days), steady-state storage stabilizes around 0.5–1 TB.

A single MinIO server with a few TB of disk handles this comfortably. No need for distributed MinIO yet.

---

## 10. Channel layer (Redis) — the streaming substrate

Live streams flow through Django Channels. The channel layer is Redis-backed in production, in-memory in tests.

### 10.1 Channel groups
- One group per execution: `execution-<id>`
- The consumer adds itself to the group on connect
- The worker / signal handlers publish to the group → all subscribers get the event

### 10.2 Best-effort publish
```python
def publish_execution_event(execution_id, event):
    try:
        channel_layer.group_send(f"execution-{execution_id}", event)
    except Exception as e:
        logger.warning("Channel publish failed: %s", e)
        # Don't crash the execution — Redis being down is not a test failure
```

This is intentional. WebSocket delivery is a UX feature, not a correctness requirement. If Redis is briefly unavailable, the execution still completes, the result still persists, and the user can refresh to see the final state.

---

## 11. Quick reference: storage and streaming changes

| Subsystem | Previous | Current Step 3 target |
|---|---|---|
| Artifact storage | Local filesystem | MinIO with pre-signed URLs |
| `TestArtifact` model | Local path field | `storage_backend` + `storage_key` |
| Stream-by-default | Yes (any execution) | No (opt-in via `stream_enabled`) |
| Video recording | Captured but stored locally | Captured, uploaded to MinIO, lifecycle-managed |
| Debug rerun | Not a distinct mode | New flag, auto-streams |
| Filesystem coupling for control signals | Control files | Redis checkpoint/stop keys |

These are the storage-and-streaming changes batched into Step 2 of the roadmap. They go together because they all hinge on the runner-container migration.
