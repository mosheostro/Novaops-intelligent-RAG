# Architecture — NovaOps Intelligent RAG

**Date:** 2026-09-20
**Status:** Design phase. Only `config.py` (and its tests) is written; the RAG pipeline is not implemented. No write of any kind has been made to OpenSearch.

The project is a filtered and reranked RAG pipeline over the NovaOps knowledge base. It combines metadata filtering (an access boundary plus subject and recency filters) with listwise reranking, and includes an evaluation that measures the separate and combined effect of both. It builds on an existing, already-populated OpenSearch Serverless index and on earlier metadata-filtering and reranking prototypes whose behavior it inherits wherever a decision was already made.

---

## 1. Architecture Decisions

| # | Topic | Decision |
|---|---|---|
| 1 | Chunking | 250 words / 50 overlap (word windows, step 200), frontmatter stripped first. Part of the corpus contract; not experimented with. Yields exactly 400 chunks. |
| 2 | Existing index | `novaops-kb` is **reused, not dropped, deleted or re-ingested.** Inspected read-only (§3): fully compatible, no blocking incompatibility. |
| 3 | Subject taxonomy | `subjects.py` + `subjects.json` (9 buckets) are authoritative. One vocabulary shared by tagger, planner and the OpenSearch filter. |
| 4 | Retrieval | Wide vector retrieval N = 10, rerank all 10. |
| 5 | Reranking | Two strategies, both kept: **static** (top 3 of 10) and **dynamic** (score ≥ 0.6, and an explicit `"not found"` if none pass — no top-1 fallback). |
| 6 | Baseline | `client.TOP_K` = 4; plain vector retrieval, access filter on, no subject filter, no rerank. |
| 7 | Eval matrix | Five configurations (§2). The two rerank strategies are never collapsed into one row. |
| 8 | Recency | Off unless a date is supplied. No default window. |
| 9 | Tagging | Per article, propagated to that article's chunks, cached in `subjects.json`. No per-chunk tagging. |
| 10 | Modules | `config.py, subjects.py, create_index.py, ingest.py, retrieval.py, planner.py, reranker.py, eval.py`. `config.py` is the central configuration module (§4). `answer()` stays in `retrieval.py`. Nothing else added. |

Access control is a hard, fail-closed boundary and is on in **every** configuration. An empty subject plan means no subject restriction (fail open).

`client.py` and `judges.py` are intentional project dependencies and stay unchanged; the same holds for `subjects.py` / `subjects.json` and the `data/` corpus.

---

## 2. Evaluation Matrix (five configurations)

Common to all: access filter on (from the question's `audience` role), recency off (no eval question carries a date), same 10 questions, same three judges + `refused()`.

| # | Config | Subject filter | Retrieval | Rerank | Final context |
|---|---|---|---|---|---|
| 1 | **baseline** | no | k-NN, k = `TOP_K` (4) | no | the 4, vector order |
| 2 | **filter-only** | yes (planner) | k-NN, k = 4 | no | the 4, vector order |
| 3 | **rerank-only** | no | k-NN, N = 10 | yes | top 3 (static) |
| 4 | **filter + rerank static** | yes | k-NN, N = 10 | yes | top 3 |
| 5 | **filter + rerank dynamic** | yes | k-NN, N = 10 | yes | every score ≥ 0.6; none → `["not found"]` |

**What each comparison isolates**

| Compare | Isolates |
|---|---|
| 1 → 2 | The subject filter alone (k held at 4 in both) |
| 1 → 3 | Reranking, together with the k 4 → 3 shrink (a deliberate part of that comparison) |
| 3 → 4 | The subject filter on top of reranking |
| 2 → 4 | Reranking on top of the filter |
| 4 → 5 | Static vs. dynamic cut (see the rerank-sharing note) |

**Design notes**
- Row 3 uses the static top-3 cut, which keeps 3 → 4 a single-variable comparison.
- **Plan once per question** and reuse across configs. Only rows 2, 4, 5 use the plan.
- **Rerank once per (question, pool)** and derive rows 4 and 5 from the same scored list. Reranking per config would make static-vs-dynamic differ by model noise as well as by the cut. Sharing makes 4 → 5 differ only in the cut and drops the rerank calls from 30 to 20. Results are still reported as separate rows.
- **Refusal handling:** for `expect_refusal` questions only `refused(answer)` is scored (both are `employee`); judges are not run. Answerable questions (8) get all three judges. The table also reports the average chunk count fed to the model, since row 5's context size floats.
- **Security assertion in the eval:** for every `employee` question, assert that no retrieved hit has `audience == "manager"`. Access is never the variable, and this makes a leak fail loudly instead of hiding in an average.
- **Cost:** about 20 rerank + 50 answer + 120 judge + 10 planner ≈ 200 model calls, plus ~50 embeddings.
- **Effect of `"not found"` on the numbers:** for an answerable question where nothing clears 0.6, row 5's context is the single string `"not found"`; `context_relevance` will score it 0 and `completeness` will drop. That is the intended cost of the reliability choice, not a bug in the eval.

---

## 3. Existing Index Compatibility Check (read-only)

Method: `GET` mapping/settings, `count`, `search` (`match_all` without vectors, plus three k-NN and four `count` queries). One embedding call for the query vector. **No index, document or setting was written.**

| Check | Result |
|---|---|
| Index exists | `novaops-kb` ✓ |
| Doc count | **400** = expected 400 chunks at 250/50 ✓ |
| Vector field | `vector`: `knn_vector`, dim **1024**, faiss HNSW, `innerproduct`; stored `mode: on_disk`, `compression_level: 32x` (server defaults, not set by the mapping). Stored vectors are unit-norm (1.0) ✓ |
| Metadata fields | `audience` keyword, `subjects` keyword (array-valued), `last_updated` date `yyyy-MM-dd`, `corpus` keyword, `source` keyword, `text` text ✓ |
| Completeness | 0 docs missing `audience`, `subjects` or `last_updated` |
| Audience split | handbook/`all` = 217 chunks; manager_playbook/`manager` = 183 chunks; corpus and audience always agree |
| Frontmatter leak | 0 chunks start with `---`; 0 contain an `audience:` line ✓ |
| Duplicates | 0 duplicate chunk texts ✓ |
| Chunk fidelity | All 400 indexed chunk texts are **identical** to what the 250/50 chunker produces from `data/` today; per-file chunk counts match for all 32 files; word counts 54–250 (369 chunks are exactly 250) |
| Metadata fidelity | `subjects` equal `subjects.json` for every chunk; `audience`, `corpus`, `last_updated` equal each file's frontmatter for every chunk |
| Access filter, live | For a manager-style question the unfiltered top-10 was **10/10 manager**; the same query with the employee filter inside the k-NN returned **10/10 `all`** |
| Subject filter, live | `employee + performance_and_feedback` → 65 chunks; k-NN returned 10 (from `making-a-career`, `titles-for-QA`, `titles-for-designers`) |
| Counts | all 400 · employee 217 · employee + subject 65 · employee + `last_updated ≥ 2025-01-01` 168. Each added clause shrinks the pool ✓ |
| Settings | 2 shards, 0 replicas, `knn: true`, `custom_doc_id_enabled: true` |

**Verdict: compatible. No blocking incompatibility. Recreation is not required and the project reuses the index and its data.** The field names `vector, text, source, corpus, audience, subjects, last_updated` are therefore fixed.

**Subject-filter power is uneven** (chunks per subject, out of 400): `managing_people` 282, `careers_titles_and_promotions` 200, `performance_and_feedback` 192, `hiring_and_onboarding` 63, `devices_security_and_systems` 63, `time_off_and_leave` 61, `company_culture_and_norms` 36, `severance_and_termination` 25, `pay_and_benefits` 23. Filtering on a narrow subject (pay, severance) removes most of the pool; filtering on `managing_people` removes almost none (70 % of chunks carry it). The eval should be read with that in mind: expect the subject filter to help pay/severance/leave questions more than manager-side ones.

**One unverified point.** The index reports `custom_doc_id_enabled: true`, while the original ingest assumed Serverless rejects caller-supplied `_id`. If custom ids work, ingest could be made idempotent with deterministic ids instead of a "refuse when populated" guard. This cannot be tested read-only. It is not needed for the current design (§4) and is left as a documented unknown.

---

## 4. Component Design

**`config.py` — central configuration (no network).** `load_dotenv(find_dotenv())`; requires `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `BEDROCK_MODEL_ID`, `BEDROCK_EMBEDDING_MODEL_ID`, `OPENSEARCH_COLLECTION`; blank counts as missing; **all** missing names are reported in one error; no defaults for region or model IDs. Validates the optional `OPENSEARCH_AWS_ACCESS_KEY_ID` / `OPENSEARCH_AWS_SECRET_ACCESS_KEY` pair (both or neither) and exposes optional `OPENSEARCH_ENDPOINT` (or `None`). Exposes only the non-secret settings as module constants (`AWS_REGION`, `BEDROCK_MODEL_ID`, `BEDROCK_EMBEDDING_MODEL_ID`, `OPENSEARCH_COLLECTION`, `OPENSEARCH_ENDPOINT`); credentials are checked but never re-exported. Validation runs at import, so **every entry point imports `config` first**: `client.py`, `judges.py` and `subjects.py` read the environment (with silent defaults for region and the embedding model) at their own import time and are not routed through `config`. New modules take region and model IDs from `config`, never from `os.environ` directly.

**`subjects.py` / `subjects.json` — unchanged.** Single source of truth for the vocabulary. The tagger reads only the first 6000 characters of each article (31 of 32 are longer), and every chunk inherits its article's tags; this is inherent to article-level tagging, and the eval's `completeness` would expose a filtered-out answer.

**`create_index.py` — non-destructive by default.** `INDEX_BODY` matches the existing mapping (`vector, text, source, corpus, audience, subjects, last_updated`). Default behavior: if the index is absent, create it; if it exists, **verify** the mapping (field types, dimension, space type) and report the doc count, then exit without changes. A destructive `--recreate` path exists only for rebuilding from scratch: it requires the explicit flag **and** a typed confirmation, and refuses to run non-interactively.

**`ingest.py` — ingest logic behind a populated-index guard.** Parse frontmatter → strip → tag via cached `load_or_tag()` (per article, zero model calls with the current cache) → chunk 250/50 → embed → bulk index. Before writing, it builds the expected records locally and compares with the live index; if the index is already populated (auto-generated ids mean an append would duplicate every chunk) it reports "already populated, N/N matches" and exits without writing. `audience` is **required** and must be `all` or `manager`: defaulting a missing audience to `all` would fail open on the one field that is a security boundary, so ingest raises instead.

**`retrieval.py` — filters, k-NN, answer.** Pure filter builders (each returns a clause list, so an inactive filter drops out): `access_filter` (employee → `audience:"all"`; manager → none), `subject_terms` (`[]` → no clause), `recency_range` (`None` → no clause), `build_filter` → `{"bool":{"must":[...]}}` or `None`. `knn_search` puts the filter **inside** the `knn` block (pre-filter, never `post_filter`) and returns hits with `text, source, corpus, audience, subjects, last_updated`. `count_candidates` reports the pool size a filter admits. `answer()`: context ordered most-relevant-first and labelled as such, with a "use a later chunk if it holds a needed detail" clause; `temperature 0.2`, `maxTokens 1000` (400 truncated the multi-step manager answers in earlier runs).

**`planner.py` — fail-open subject planner.** Forced `pick_subjects` tool over the imported `SUBJECTS`; recall-biased; `[]` for broad/unmappable; invalid labels dropped. Uses the shared `bedrock` client from `client.py`.

**`reranker.py` — listwise reranker + the cut.** `rerank_all` (one forced `rank` call, all candidates, whole chunks, scores clamped to 0–1, missing or out-of-range index → 0.0, stable order); `rerank(query, candidates, top_k)`; plus two pure functions for the two cuts — static top-k and dynamic threshold (which returns the `"not found"` sentinel when nothing passes). Placing the cuts here rather than inside `eval.py` makes them deterministically testable. The scoring prompt ("score each candidate 0.0–1.0 for how well it helps answer the query") is kept as in the earlier prototype: the 0.6 threshold is calibrated to that wording.

**`eval.py` — the five-configuration harness.** Constants local to the file: `RETRIEVE_N = 10`, `STATIC_K = 3`, `MIN_SCORE = 0.6`, baseline k = `client.TOP_K`. Five configs (§2), plan-once, rerank-once-per-pool, `n_chunks` column, refusal path via `refused()`, employee security assertion. Prints the comparison table.

---

## 5. Hard Security Constraints vs. Quality Mechanisms

**Fail closed (security):** the access filter — inside the k-NN query, in every path, tested with no model call. Also the ingest-time audience default (missing → error, not `all`).

**Fail open (quality):** subject filter (`[]` → search everything), recency (off), reranking (reorders only, never widens access).

**Reliability rule:** the dynamic cut never falls back to the top-1; low-confidence retrieval becomes an explicit `"not found"` context instead of apparently valid evidence.

Relevance, answerability and refusal stay separate: `faithfulness`, `context_relevance`, `completeness` and refusal are separate columns, never folded together.

---

## 6. Data Flow

```
data/*.md ─► ingest.py ─► frontmatter → audience, last_updated, corpus
                       ─► subjects.load_or_tag()   [cache: subjects.json]
                       ─► chunk 250/50 ─► embed_text() ─► bulk index ─► novaops-kb (already populated, reused)

eval.py ─► planner.plan_subjects(q)              [imports subjects.SUBJECTS; once per question]
        ─► retrieval.build_filter(role, subjects, date)
        ─► retrieval.knn_search(...)             [k=4 for rows 1–2, N=10 for rows 3–5]
        ─► reranker.rerank_all(q, candidates)    [once per (question, pool)]
        ─► reranker cuts: static top-3 | dynamic ≥0.6 | "not found"
        ─► retrieval.answer(q, contexts)
        ─► judges.* / judges.refused
```

Shared state between modules: only `subjects.SUBJECTS`.

---

## 7. Failure Modes and Mitigations

| Failure | Mitigation |
|---|---|
| Employee sees manager chunks | Access clause inside the k-NN filter in every path; deterministic polarity tests; live check; eval assertion |
| Missing `audience` in a document silently becomes `all` | `ingest.py` raises unless `audience ∈ {all, manager}` |
| Script destroys the shared index | `create_index.py`/`ingest.py` are non-destructive by default; `--recreate` needs flag + typed confirmation and refuses non-interactive runs |
| Re-ingest duplicates chunks | Populated-index guard in `ingest.py` |
| Subject filter hides the answer | Recall-biased planner; `[]` → no clause; `completeness` watches for it; narrow-vs-broad subject effect documented (§3) |
| Tagger/planner vocabulary drift | Single `SUBJECTS` import; import-identity test |
| Frontmatter in embeddings | Stripped before chunk/embed; verified 0 leaks in the live index |
| Post-filtering | Filter inside the `knn` block only |
| Low-confidence retrieval treated as evidence | Dynamic cut returns `["not found"]`, no top-1 fallback |
| Reranker omits / mis-indexes a candidate | Missing or out-of-range → 0.0; per-entry parse guarded; stable sort |
| Static-vs-dynamic difference is really model noise | Rerank once per pool; both cuts read the same scores |
| `refused()` keyword heuristic misclassifies | Read the printed answers; treat refusal columns as indicative |
| Approximate recall from on-disk 32x quantized vectors | Inherent to the existing index; unchanged by this work |
| Cold-start timeout | Handled in `client.py` (`timeout=120`, retries) |
| Missing or blank configuration masked by a default in an existing module | `config.py` validates all six required variables first and raises one error naming every missing one; entry points import it before `client`, `judges`, `subjects` |

---

## 8. Configuration

Required: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `BEDROCK_MODEL_ID`, `BEDROCK_EMBEDDING_MODEL_ID`, `OPENSEARCH_COLLECTION`. Optional: `OPENSEARCH_ENDPOINT` (skips the name lookup) and the `OPENSEARCH_AWS_*` credential pair (both or neither; used to sign OpenSearch calls when the collection lives in a different account than Bedrock). `config.py` enforces this at startup; `.env.example` documents it with blank values and the optional variables commented out. Dependencies: `boto3`, `python-dotenv`, `opensearch-py` (`requirements.txt`).

---

## 9. Tests

**Deterministic (no model, no network)**
1. `access_filter`: employee → `audience:"all"`; manager → no clause.
2. `build_filter("employee", [], None)` → access clause only; `("manager", [], None)` → `None`.
3. `build_filter("employee", ["pay_and_benefits"], "2024-01-01")` → access + `terms` + `range` in one `bool.must`.
4. Planner and tagger use the same `SUBJECTS` object.
5. `parse_frontmatter` leaves no `---` block; chunker yields **400** chunks over `data/` at 250/50; missing/invalid `audience` raises.
6. Static cut keeps exactly k; dynamic cut keeps all ≥ 0.6 in order; dynamic with none passing returns `["not found"]` (not the top-1).
7. Reranker with a stubbed tool response: omitted index → 0.0, out-of-range ignored, scores clamped, stable ties, malformed entry skipped.
8. `create_index.py` / `ingest.py` refuse to delete or append without the explicit path (unit-level, no AWS).
9. `config.load_config`: all six required present → non-secret settings returned; every missing name reported together; blank counts as missing; no default for region or model IDs; the optional credential pair is both-or-neither. **Implemented** in `tests/test_config.py` (stdlib `unittest`, 13 tests, no network); run with `python -m unittest`.

**Integration (live, read-only)**
10. Index verify passes: mapping types/dim, 400 docs, per-file counts match the local build.
11. Employee k-NN never returns `audience: manager`; adding a soft clause never increases `count_candidates`.

**Eval**
12. `ACCESS_REVIEW` and `UNANSWERABLE_AWS` are refused in the mix rows.
13. The three manager questions are not refused and have `completeness > 0` in rows 4 and 5.
14. The mix improves `context_relevance` and/or `faithfulness` over baseline without `completeness` collapsing.

---

## 10. Repository Boundary

- **Public / trackable:** `data/`, `subjects.py`, `subjects.json`, `client.py`, `judges.py`, `config.py`, `requirements.txt`, `.env.example`, `CLAUDE.md`, `README.md`, `setup.sh`, `setup.ps1`, `docs/`, `tests/`, `.gitignore`, and the application modules (`create_index.py`, `ingest.py`, `retrieval.py`, `planner.py`, `reranker.py`, `eval.py`) as they are implemented.
- **Local only (git-ignored, kept on disk):** `.env`, local working notes and reference material, virtual environments and caches.
- **Credentials:** none are committed. `.env` is ignored; `.env.example` holds blank placeholders only.

---

## 11. Open Items (none blocking implementation)

1. Caller-supplied `_id` on this collection is unverified (§3). The default design does not depend on it.
2. Row 3's cut is an explicit choice (static top-3, §2); a dynamic rerank-only row could be added later.
