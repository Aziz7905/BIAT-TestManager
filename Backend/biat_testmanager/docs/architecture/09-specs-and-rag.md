# 09 — Specs and RAG

**Specification ingestion, parsers, chunking, pgvector retrieval. The RAG layer that grounds AI generation.**

---

## 1. Why specs are first-class data

Banking applications are heavily specified. Every feature has a requirements document. Tests must trace back to those requirements. The platform's specs layer:

1. **Ingests** specs from PDFs, DOCX, XLSX, CSV files, URLs, or directly from Jira tickets
2. **Parses** them into structured records that humans can review and approve
3. **Stores** approved specs as canonical `Specification` records linked to the project
4. **Chunks and embeds** them for retrieval (semantic search via pgvector)
5. **Serves** them as RAG context for the AI layer (Phase D and Phase E)

The specs layer is the **knowledge backbone** for AI generation. Without it, the AI is generating tests blind.

---

## 2. The four-stage ingestion pipeline

```
  ┌──────────────────────────┐
  │  1. SpecificationSource  │   ← raw upload or URL
  │     (parser_status)      │
  └────────────┬─────────────┘
               ▼
  ┌──────────────────────────────────┐
  │  2. SpecificationSourceRecord    │   ← parser output, awaits human review
  │     (status: pending_review)     │
  └────────────┬─────────────────────┘
               ▼
  ┌──────────────────────────┐
  │  3. Specification         │   ← canonical record after import
  │     (index_status)        │
  └────────────┬─────────────┘
               ▼
  ┌──────────────────────────┐
  │  4. SpecChunk + embedding │   ← pgvector indexed for retrieval
  └──────────────────────────┘
```

### 2.1 Stage 1 — Source upload
The user uploads a file (PDF, DOCX, XLSX, CSV) or provides a URL. The platform stores the original in `SpecificationSource.file` (or `source_url`).

`parser_status` starts as `pending`.

### 2.2 Stage 2 — Parse to records
The parser (one per source type) extracts structured data from the source:
- **PDF parser** — uses text extraction; handles structured documents and free-form prose
- **DOCX parser** — Office Open XML walker; respects headings as section breaks
- **XLSX parser** — each row becomes a record (test step, requirement, etc.)
- **CSV parser** — simplest — one row per record
- **URL parser** — fetches the page, extracts main content via boilerplate-removal
- **Jira parser** — fetches a ticket via the Jira integration, treats summary + description + comments as the spec body

Each parsed item becomes a `SpecificationSourceRecord` with `status='pending_review'`.

### 2.3 Stage 3 — Human review and import
A QA team member reviews the records. They can:
- Edit the extracted content
- Approve a record → `status='imported'` → triggers creation of a `Specification` row
- Reject a record → `status='rejected'`

This human-in-the-loop step matters: parsers are imperfect, especially for PDFs with complex layouts. The review queue catches garbage before it becomes canonical.

### 2.4 Stage 4 — Indexing for retrieval
After import, the `Specification` is chunked and embedded:
1. Spec body is split into sentence-windowed chunks (config: `SPEC_CHUNK_MAX_CHARS=1400`, `SPEC_CHUNK_OVERLAP_CHARS=120`)
2. Each chunk is embedded with `BAAI/bge-m3` (1024-dim vector)
3. Chunks are stored in `SpecChunk` with HNSW cosine index in pgvector
4. `Specification.index_status` flips to `indexed`

The indexing is **idempotent**: re-indexing replaces all chunks atomically.

---

## 3. The chunking strategy

### 3.1 Why chunking
LLMs have context windows. A 50-page bank specification doesn't fit. Even when it does, dropping the whole spec into every prompt is wasteful (cost) and noisy (less relevant content drowns the relevant content).

Chunking + retrieval gives us: take the user's query, find the 5–15 most relevant chunks, inject only those.

### 3.2 The chunking algorithm
**Sentence-windowed with overlap:**
1. Split the spec into sentences (using a text segmenter)
2. Group consecutive sentences into chunks until the chunk would exceed `SPEC_CHUNK_MAX_CHARS` (1400)
3. Each chunk overlaps the previous by `SPEC_CHUNK_OVERLAP_CHARS` (120 chars) to preserve context across boundaries
4. Each chunk is tagged with its `chunk_type` — paragraph / heading / list / table_cell — based on the source structure

### 3.3 Why these sizes
- **1400 chars** — fits comfortably under most embedding model token limits with margin for safety
- **120-char overlap** — enough to maintain coherence at chunk boundaries without dramatic redundancy

These are tunable per project if a particular spec style needs different settings.

---

## 4. The embedding model: `BAAI/bge-m3`

### 4.1 Why this model
- **Multilingual** — handles French and Arabic content (relevant for BIAT's Tunisian operations)
- **High dimensional** (1024-dim) — captures fine-grained semantic distinctions
- **Locally runnable** — under `HuggingFace_models/` on the server, no API call per embed
- **Strong on retrieval benchmarks** — chosen for performance on RAG tasks specifically

### 4.2 Local inference
Setting `SPEC_EMBEDDING_LOCAL_FILES_ONLY=true` forces the platform to use the bundled model files, never downloading from HuggingFace at runtime. This matters in the bank's potentially-air-gapped network.

### 4.3 Future swap
If a better model emerges, swap by:
1. Adding a new `EmbeddingModel` row
2. Re-indexing affected specs (idempotent)
3. Updating `SPEC_EMBEDDING_MODEL_NAME` in settings

The `SpecChunk.embedding_model` FK lets the platform support multiple embedding models simultaneously during a transition.

---

## 5. pgvector retrieval

### 5.1 The index
```sql
CREATE INDEX ON spec_chunks USING hnsw (embedding vector_cosine_ops);
```

HNSW (Hierarchical Navigable Small World) is the right index choice for fast approximate nearest-neighbor search at this scale. The `vector_cosine_ops` operator class uses cosine distance, which is the standard for embedding similarity.

### 5.2 The query
```python
def retrieve_chunks(project_id, query: str, k: int = 10) -> list[SpecChunk]:
    query_embedding = embed(query)  # 1024-dim
    return SpecChunk.objects.filter(
        specification__project_id=project_id,
    ).annotate(
        distance=CosineDistance('embedding', query_embedding),
    ).order_by('distance')[:k]
```

Note the **project scope** — retrieval is always scoped to the asking user's accessible projects. No cross-project leakage.

### 5.3 Top-k tuning
- `test_design` use case: k=5–10 (small, focused context)
- `agent` use case (Phase E): k=10–20 (broader context as the agent explores)
- `rca` use case: k=3–5 (just the relevant section for the failed step)

Tunable per call. No global setting.

---

## 6. MLflow telemetry

Every embedding run logs to MLflow:
- Model name and version
- Project id, specification id
- Number of chunks created
- Total tokens embedded (approximate)
- Duration in ms
- Success / failure with error class

Why: when something goes wrong (a spec doesn't get indexed, retrieval returns nothing), the MLflow trace is the primary debugging surface. A manager can see "spec X started indexing at 10:03, took 4 minutes, produced 47 chunks, completed successfully."

Failures **don't crash the API request** — they're logged and propagated as `index_status='failed'` on the spec, with details fetchable via a separate endpoint.

---

## 7. The API surface

### 7.1 Source endpoints
```
POST   /api/specs/sources/                    # upload a source (file or URL)
GET    /api/specs/sources/                    # list, paginated, scoped to user's projects
GET    /api/specs/sources/<id>/               # detail
POST   /api/specs/sources/<id>/parse/         # trigger parsing (or re-parse)
GET    /api/specs/sources/<id>/records/       # list source records pending review
PATCH  /api/specs/source-records/<id>/        # edit / approve / reject a record
POST   /api/specs/source-records/<id>/import/ # turn an approved record into a Specification
```

### 7.2 Specification endpoints
```
GET    /api/specifications/                   # list, project-scoped
GET    /api/specifications/<id>/              # detail (no embeddings by default)
PATCH  /api/specifications/<id>/              # update body — re-triggers indexing
DELETE /api/specifications/<id>/              # soft-delete (cascade chunks)
POST   /api/specifications/<id>/index/        # trigger / re-trigger indexing
GET    /api/specifications/<id>/chunks/       # list chunks (optional embedding via ?include=embedding)
```

### 7.3 Retrieval endpoint (planned for Phase D)
```
POST   /api/specs/retrieve/
  body: {project_id, query, k}
  response: [{chunk_id, content, similarity, specification_title}]
```

Step 4A uses the existing internal retrieval service first: project-scoped `Specification` / `SpecChunk` search from the AI generation workflow. A public retrieval endpoint can still be added later for UI search, but AI generation does not need a separate RAG table or a new embedding store.

---

## 8. Traceability

A `TestCase` can link to multiple `Specification` rows via M2M. This gives the platform two-way traceability:
- From a spec → which test cases cover it
- From a test case → which specs justify it

When a spec changes, the platform can flag all linked test cases for re-review. When a test fails, the failure can be reported in the context of the requirement it was meant to verify.

This is bank-grade traceability and a regulatory advantage.

---

## 9. Why specs power AI generation

The specs layer was built before any AI work. It seems like overkill for a non-AI platform. It isn't.

When the AI generates a test from a Jira ticket:
1. The ticket says: *"Add transfer limit of 10,000 TND per day for retail customers"*
2. The agent retrieves: existing specs about transfer flows, customer types, limit enforcement
3. With that context, the LLM produces tests that respect the existing rules
4. Without that context, the LLM hallucinates plausible-but-wrong tests

**The RAG layer is the difference between an AI feature that works and one that produces nonsense.** The spec ingestion pipeline exists to populate that RAG layer with real, verified, project-scoped knowledge.

This is also why Layer 1 (test management) is built before Layer 3 (AI agent): the AI needs the data Layer 1 produces.

---

## 10. Where the specs code lives

| Concern | Path |
|---|---|
| Models | `apps/specs/models/` |
| Parsers | `apps/specs/services/parsers/` (one per source_type) |
| Chunking | `apps/specs/services/chunking.py` |
| Embeddings | `apps/specs/services/embeddings.py` |
| Indexing orchestration | `apps/specs/services/indexing.py` |
| Retrieval (planned) | `apps/specs/services/retrieval.py` |
| MLflow integration | (within services above) |
| Views | `apps/specs/views/` |
| Serializers | `apps/specs/serializers/` |

The `services/` directory is heavy intentionally — chunking, embedding, retrieval are non-trivial workflows that would clutter views or models. They live in services, well-tested, with clear inputs and outputs.
