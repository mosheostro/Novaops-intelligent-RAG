# Evaluation Domain Model — Design (Pydantic domain-contract layer)

**Status:** **Design ready for implementation.** No code has been changed by this document. The model hierarchy (§4), the semantic decisions (§6), and the per-function boundary (§10) are all resolved; §11 is the checklist the implementation task should follow.
**Scope:** The evaluation subsystem's *result* (what `eval.py` returns), not its computation. Retrieval, reranking, planning, judging and security enforcement are unchanged.

---

## 1. Purpose

`eval.py` currently returns a nested structure built from plain `dict`s and `list`s. That structure works, but it is an **implicit contract**: every consumer (the CLI `report()`, and eventually a dashboard, an API, or an MCP tool) has to know the exact keys, their types, and which keys only exist in some branches (`"refusal_ok"` vs `"faithfulness"`) by reading `eval.py`'s source, not by reading a type.

This document proposes a **Pydantic domain-contract layer** that sits between the existing evaluation computation and every consumer:

```
RAG / evaluation computation (unchanged)
        ↓
Pydantic domain models   ← this document
        ↓
 ┌───────────┬──────────────┬───────────────┬─────┐
 CLI report   future Web UI   future API/MCP   ...
```

The boundary this establishes: **once evaluation produces an `EvaluationResult`, no consumer needs to know anything about `eval.py`'s internals** — how candidates are pooled, how reranking is shared across configs, how "not found" is represented internally. They read typed objects.

---

## 2. Current problem

Concretely, today's result (see `eval.py::evaluate`) is:

```python
{
  "metadata": {...},
  "questions": {
    "<question_id>": {
      "question": ..., "audience": ..., "expect_refusal": ..., "planned_subjects": [...],
      "configs": {
        "baseline": {
          "answer": ..., "contexts": [...], "n_chunks": 4,
          "metrics": {"faithfulness": 0.8, "faithfulness_reason": ..., ...}  # OR {"refusal_ok": True}
          "retrieval": {
            "audience": ..., "subjects_applied": ..., "top_k_requested": 4,
            "candidate_pool": [{...8 fields...}, ...],
            "selected": [{...8 fields..., "final_rank": 0}, ...],
            "security_violation": False, "security_violating_sources": [],
          },
        },
        "filter-only": {...}, "rerank-only": {...},
        "filter + rerank static": {...}, "filter + rerank dynamic": {...},
      },
    },
  },
  "summary": {"baseline": {...}, ...},
}
```

Four concrete problems, found by reading `eval.py` and `tests/test_eval.py` rather than assumed:

1. **`metrics` has two incompatible shapes** depending on `expect_refusal`, with no field announcing which one you got — a consumer has to `"refusal_ok" in metrics`.
2. **`n_chunks = len(contexts)` conflates two different things.** For the dynamic cut, when nothing clears `MIN_RERANK_SCORE`, `select_context` returns `contexts = ["not found"]` — a **presentation string** fed to `retrieval.answer()` so it produces a grounded refusal. `n_chunks` then reports `1`, even though **zero chunks were actually selected**. `summarize()`'s `n_chunks_avg` inherits this distortion.
3. **`candidate_pool` and `selected` are two lists of the same shape**, and the only thing that tells them apart is which dict key you found them under, plus a `final_rank` key that exists only on entries in `selected`. Nothing stops a future consumer from reading `final_rank` off a pool candidate that never had one set (it just isn't there — a silent `KeyError`, not a type error).
4. **Security is one boolean field inside `retrieval`**, indistinguishable in shape from a quality score, even though `docs/architecture-discovery.md` §5 and `CLAUDE.md` both say access control is a hard invariant, categorically different from `faithfulness`/`context_relevance`/`completeness`.

None of this is a bug — `eval.py` is correct and tested (33 tests). It is a **missing type boundary**.

---

## 3. Design goals

- **Explicit domain contract** — every field a consumer can read is declared, typed, and documented once.
- **Semantic clarity over structural uniformity** — a refusal question's result and a content question's result are allowed to look different, because they *are* different; no field exists just to keep two models "the same shape."
- **Security is not a quality score** — represented as its own small, always-present concept, never merged into the metrics bag.
- **Future consumer independence** — a UI/API/MCP layer built later reads `EvaluationResult` and gets IDE-level autocomplete and validation; it never re-derives what `eval.py` "probably" returns.
- **Preserve the existing functional architecture** — no `EvaluationEngine`, no repository/service/factory/mapper layer. `eval.py` stays a set of functions; they just build and return typed objects instead of dicts.
- **Minimal modeling** — a dict becomes a model only where it represents a real, reused domain concept (see §5 for the ones that *don't* qualify).
- **Models are domain objects, not serialization wrappers** — used inside Python for their structure and validation; JSON is one output format among several (see §8).

---

## 4. Proposed domain model

```
EvaluationResult
 ├── metadata: EvaluationMetadata
 ├── questions: dict[str, QuestionResult]      # keyed by question id
 └── summary:   dict[ConfigName, ConfigSummary] # keyed by config name

QuestionResult
 ├── id, question, audience, expect_refusal, key_facts, planned_subjects
 └── configurations: dict[ConfigName, ConfigurationResult]

ConfigurationResult
 ├── name: ConfigName
 ├── retrieval:  RetrievalResult
 │    ├── audience, subjects_applied, top_k_requested
 │    ├── candidates: list[Candidate]
 │    └── security: SecurityAudit
 ├── selection:  SelectionResult
 │    ├── status: "selected" | "not_found"
 │    ├── chunks: list[SelectedChunk]           # SelectedChunk wraps a Candidate + final_rank
 │    └── context_texts: list[str]              # what was actually sent to answer()
 ├── answer: str
 └── evaluation: ContentEvaluation | RefusalEvaluation   # discriminated by `kind`

Candidate            # a chunk as retrieval returned it — no selection decision made yet
SelectedChunk        # { candidate: Candidate, final_rank: int } — exists only after selection
SecurityAudit        # { violation: bool, violating_sources: list[str] }
ContentEvaluation    # { kind: "content", faithfulness, faithfulness_reason, context_relevance, ... }
RefusalEvaluation    # { kind: "refusal", refusal_ok: bool }
EvaluationMetadata   # question_count, configs, candidate_pool_size, static_top_k, dynamic_threshold, baseline_top_k
ConfigSummary        # n_chunks_avg, faithfulness_avg, context_relevance_avg, completeness_avg, refusal_ok_avg, security_violations

ConfigName = Literal["baseline", "filter-only", "rerank-only",
                     "filter + rerank static", "filter + rerank dynamic"]
```

This is 10 models total (2 are the discriminated-union pair) plus one `Literal` type alias — not a class per nested dict in today's structure (today's structure has more distinct dict shapes than this; several collapse, explained in §5/§6).

---

## 5. Model responsibilities

**`Candidate`** — a chunk as OpenSearch/reranking returned it, before any selection decision.
- *Represents:* one retrieved chunk plus its retrieval and (optionally) reranking signal.
- *Why it exists:* the exact same 9-field shape is built once per hit (`hits_to_candidates`) and then read from five different places (all five configs, plus the security audit) without ever changing meaning. That repetition across independent call sites is precisely what "deserves a model" — a plain dict here has no enforcement that all nine keys stay present and correctly typed everywhere it's threaded through.
- *Fields:* `text, source, corpus, audience, subjects, last_updated, vector_score, vector_rank, rerank_score`.
- *Owns:* the content and metadata of one retrieved chunk.
- *Does not own:* whether it was selected, or its rank in a particular selection cut — see `SelectedChunk`.

**`SelectedChunk`** — a `Candidate` plus the fact that a selection policy chose it, and where it landed.
- *Represents:* the outcome of applying static-top-k or dynamic-threshold to a ranked pool.
- *Why separate from `Candidate`:* `final_rank` is meaningless before selection, and — critically — the **same** pool (same `Candidate` objects) is selected two different ways for the filter+rerank static and dynamic configs (§6). If `final_rank` were a field on `Candidate` itself, writing it for one cut would either mutate a value the other cut also reads, or require defensive copying scattered through the calling code (which is exactly what today's `_rank_selected` does by hand, quietly, with a comment explaining why). Making `SelectedChunk` a separate, always-freshly-built wrapper makes that defensive copy structural instead of a comment.
- *Fields:* `candidate: Candidate`, `final_rank: int` (0-based, within *this* selection).
- *Owns:* the selection outcome for one candidate in one cut.
- *Does not own:* the candidate's retrieval data (delegates to `.candidate`).

**`SecurityAudit`** — whether this retrieval, for this question and role, returned anything it should not have.
- *Represents:* the outcome of `audience_violation(pool, role)` — an audit of the **entire retrieved pool**, not just what was selected (§6).
- *Why it exists:* the current architecture (`docs/architecture-discovery.md` §5, `CLAUDE.md`) treats access control as a hard, binary invariant, categorically different from a 0–1 quality score. A model makes that difference visible in the type system, not just in a docstring — a consumer cannot accidentally average `security_violation` into a metrics report the way it currently could accidentally treat `metrics["refusal_ok"]` (a bool) like a score.
- *Fields:* `violation: bool`, `violating_sources: list[str]`.
- *Owns:* the audit outcome only. It never filters or corrects anything — same as today's `audience_violation()`, which reports, never fixes.

**`ContentEvaluation` / `RefusalEvaluation`** — the two, and only two, ways a config's answer is scored.
- *Represents:* judge output for an answerable question (`ContentEvaluation`) or the refusal check for an `expect_refusal` question (`RefusalEvaluation`).
- *Why two models instead of one:* forcing both into one model means either a pile of `Optional` fields that are meaningless in one branch (rejected explicitly — see §3, §6), or silently allowing a `ContentEvaluation`-shaped object to be missing its scores. Two small models with a `kind` discriminator let a consumer (or Pydantic itself, via `Field(discriminator="kind")`) branch exhaustively and correctly, and each model only ever has fields that are always meaningful.
- *Fields:* `ContentEvaluation`: `kind: Literal["content"]`, `faithfulness, faithfulness_reason, context_relevance, context_relevance_reason, completeness, completeness_reason`. `RefusalEvaluation`: `kind: Literal["refusal"]`, `refusal_ok: bool`.
- *Owns:* the judged outcome for one config's answer.
- *Does not own:* which judges were *supposed* to run for this question — that's a property of the question (`expect_refusal`), not of the evaluation result.

**`RetrievalResult`** — what came back from OpenSearch for this config, and whether it was safe.
- *Represents:* the retrieval side of a configuration: the role, the filters that were actually applied, and the raw pool.
- *Why it exists as its own model (and why it includes `security`, not just candidates):* "what did we retrieve" and "was it safe" are two questions about the *same* pool, answered by the *same* call (`audience_violation` reads the pool `RetrievalResult` already holds). Splitting security into a third top-level sibling model would force every caller to keep two lists (`candidates`, `security.violating_sources`) in sync by hand; nesting it here means a `RetrievalResult` is self-consistent by construction.
- *Fields:* `audience, subjects_applied, top_k_requested, candidates: list[Candidate], security: SecurityAudit`.
- *Owns:* everything about the retrieval step, for one config.
- *Does not own:* the selection cut, or the answer — see `SelectionResult`, `ConfigurationResult`.

**`SelectionResult`** — what was chosen from that retrieval, and what was actually sent to the model.
- *Represents:* the selection policy's output: static top-k, dynamic threshold, or (for baseline/filter-only) the trivial "everything retrieved" cut.
- *Why separate from `RetrievalResult`:* selection is a distinct decision, made *after* retrieval, using a signal retrieval doesn't need to know about (`rerank_score` for rerank configs; plain retrieval order otherwise). Two different `SelectionResult`s (static and dynamic) are built from the literal same `RetrievalResult` for configs 4 and 5 — collapsing the two models would mean re-deriving or duplicating the pool every time the cut changes.
- *Fields:* `status: Literal["selected", "not_found"]`, `chunks: list[SelectedChunk]`, `context_texts: list[str]`.
- *Owns:* the selection outcome and the literal text handed to `answer()`.
- *Does not own:* the pool it selected from (that's `RetrievalResult.candidates`) — a `SelectedChunk.candidate` links back if needed, but `SelectionResult` doesn't duplicate the full pool.

**`ConfigurationResult`** — everything produced for one (question, config) pair; the main object a future UI renders.
- *Represents:* one row of the evaluation matrix for one question — retrieval, selection, the generated answer, and its judgment.
- *Fields:* `name: ConfigName`, `retrieval: RetrievalResult`, `selection: SelectionResult`, `answer: str`, `evaluation: ContentEvaluation | RefusalEvaluation`.
- *Owns:* the full, self-contained result of running one config on one question. A single `ConfigurationResult` can be handed to a UI widget with no other context and remain meaningful (it carries its own `name`, even though it will also sit under a `ConfigName`-keyed dict — a deliberate, cheap redundancy; see §6, "configuration identity").
- *Does not own:* `n_chunks` as **stored state**. **Decided:** it is a read-only computed property, `len(self.selection.chunks)`, never a field written at construction time — so it can never drift out of sync with `selection.chunks` the way today's separately-tracked `n_chunks` conflates with `len(contexts)` (§2, §6).

**`QuestionResult`** — everything produced for one question, across all five configs.
- *Fields:* `id, question, audience, expect_refusal, key_facts, planned_subjects, configurations: dict[ConfigName, ConfigurationResult]`.
- *Why `id` and `key_facts` are added* (neither is in today's `evaluate_question()` return dict — `id` is currently only the *outer* dict's key, and `key_facts` isn't threaded through at all): a `QuestionResult` extracted on its own (e.g. passed to a UI component) must be able to say which question it is and what it was supposed to answer, without the caller also having to keep the original question record around. Both values already exist on the input `q` dict; this only decides to carry them forward. **Decided (not merely proposed):** `key_facts` stays in `QuestionResult` — it costs one extra field, already exists on every question record, and directly serves a future dashboard/API/MCP consumer wanting to show "what the answer was expected to cover" without a side-channel back to `data/eval_questions.jsonl`.
- *Owns:* the question's own data plus its five configuration outcomes.
- *Does not own:* cross-question aggregation — that's `summary`, computed once at the `EvaluationResult` level.

**`EvaluationResult`** — the top-level contract; what `evaluate()` returns and what every consumer holds.
- *Fields:* `metadata: EvaluationMetadata`, `questions: dict[str, QuestionResult]`, `summary: dict[ConfigName, ConfigSummary]`.
- *Owns:* one complete evaluation run, as a finished, self-describing snapshot.
- *Does not own:* presentation. `report()` (and any future UI/API) reads this object; nothing here formats text or prints.

**`EvaluationMetadata`**, **`ConfigSummary`** — small, flat records; not elaborated further since they map 1:1 onto existing dict shapes with no semantic ambiguity to resolve.

### Deliberately *not* modeled

- **The five `CONFIG_NAMES` strings** stay a `Literal` type alias, not an `Enum` class. A `Literal["a", "b", ...]` gives Pydantic validation, static type-checking, and dict-key typing with zero new class machinery; an `Enum` would additionally need `.value` unwrapping at every JSON boundary for no behavioral gain here.
- **No `Config`/`Repository`/`Service`/`Mapper`/`Factory`.** Building an `EvaluationResult` stays the job of `eval.py`'s existing functions (`evaluate_question`, `run_config`, etc.), each returning one more level of the model instead of one more level of dict.

---

## 6. Important semantic decisions

**Candidate vs. `SelectedChunk`.** Kept distinct (§5). A `Candidate` can never carry a `final_rank`; a `SelectedChunk` can never exist without one. This is enforced by the type, not by convention — today's convention ("only entries under `"selected"` have `final_rank`") is enforced by nothing.

**Static vs. dynamic selection share one retrieval, not one selection.** For configs 4 and 5, `eval.py` retrieves and reranks the pool exactly once (§ "call-sharing rules" in `eval.py`'s own docstring) and cuts it two ways. The model reflects this directly: **one `RetrievalResult`, two `SelectionResult`s** — one embedded in each of the two `ConfigurationResult`s. Nothing about `RetrievalResult` changes between the static and dynamic rows; only `SelectionResult` does. (Whether the *same* `RetrievalResult` object is literally shared by reference between the two `ConfigurationResult`s, or built twice with identical values, is a small implementation choice for later — see §10 — and doesn't affect the model shape.)

**"not found" is not a chunk.** `SelectionResult.status` is `"not_found"` exactly when `chunks == []`; `context_texts` is still `["not found"]` in that case, because that literal string is what `retrieval.answer()` needs to produce its existing "say so plainly" behavior, and this design does not change `retrieval.answer()`. The key move: **the domain truth (`chunks`, `status`) and the prompt-presentation value (`context_texts`) are two different fields**, so a consumer computing "how many chunks were used" reads `len(chunks)` (correctly `0`), never `len(context_texts)` (which stays `1` for a reason that has nothing to do with chunk count).

**`n_chunks` is a computed property, not stored state — decided.** `ConfigurationResult.n_chunks` is `len(self.selection.chunks)`, read-only, always consistent with `chunks` by construction; it is never written or passed in at construction time. `summarize()` averages over this corrected value for `n_chunks_avg` — a small, intentional improvement in the *reported number* (not in retrieval/ranking/selection behavior), flagged explicitly since the task asks not to change evaluation behavior: this changes only what a downstream average measures (real selected-chunk count, including the correct `0` for a `not_found` row), not what was retrieved, ranked, or selected.

**Answer contexts.** `context_texts` on `SelectionResult` is the single field that plays the role today's `contexts` key plays for both `run_config` (building the answer prompt) and `score_answer` (judging on that same text). It is intentionally *not* derived from `chunks` when `status == "not_found"`, and intentionally *is* derived from `chunks` (`[c.candidate.text for c in chunks]`) otherwise — one field, two possible provenances, documented here rather than hidden in a helper function.

**Security audit.** Lives on `RetrievalResult` (§5), computed over the *whole pool*, not just `selection.chunks` — matching `audience_violation(pool, role)` today, which audits everything retrieved, since a leak into the pool is a security fact regardless of whether that particular chunk happened to be selected for the answer.

**Normal vs. refusal evaluation.** A discriminated union (`ContentEvaluation | RefusalEvaluation`, tagged by `kind`), not one model with optional fields (§5). Which variant a `ConfigurationResult` gets is fully determined by `QuestionResult.expect_refusal` — never mixed within one question's five configs.

**Configuration identity.** `ConfigName` is a single `Literal` type reused three ways: as the key type for `QuestionResult.configurations`, as the key type for `EvaluationResult.summary`, and as the `name` field on `ConfigurationResult` itself. The redundancy (a `ConfigurationResult` knows its own name *and* sits under a dict keyed by that name) is deliberate: a `ConfigurationResult` handed to a UI component in isolation must remain self-describing.

**Summary.** Computed once, by a plain function (today's `summarize()`, largely unchanged in logic), and **stored** on `EvaluationResult.summary` rather than exposed as a lazy computed property recomputed on every access. An `EvaluationResult` represents one finished run — a historical snapshot — and recomputing judge-score averages on every read buys nothing and risks the average silently drifting if `questions` were ever mutated after construction (guarded against entirely if the models are frozen — see §10).

---

## 7. Data flow

```
knn_search() / rerank_all()   raw dicts, tuples — UNCHANGED, retrieval.py/reranker.py untouched
        ↓
eval.py's functions            build Candidate / SelectedChunk / SecurityAudit / ... objects
        ↓
ConfigurationResult, QuestionResult   assembled per question, per config — same call-sharing rules as today
        ↓
EvaluationResult                returned by evaluate() — the one contract
        ↓
report()            future Dashboard          future API / MCP tool
(reads .summary,    (reads .questions[...]     (serializes EvaluationResult.model_dump()
 .metadata; unchanged  .configurations[...]     or .model_dump_json() at the boundary)
 CLI table)            for per-chunk detail)
```

The Pydantic layer starts **inside `eval.py`**, at the point where OpenSearch hits and reranker output are converted into domain objects (`hits_to_candidates`'s successor). `retrieval.py`, `reranker.py`, `planner.py`, `subjects.py` keep their current plain dict/tuple/list contracts — they are not part of this domain model and are not touched.

---

## 8. Serialization boundary

Pydantic models are used here as **in-process domain objects**: `report()` and any future in-process consumer read `.attribute` access, get IDE autocomplete, and get validation errors immediately if a value is wrong shape — not a `KeyError` three function calls later.

JSON only appears where something actually needs to leave the process: a future API response, an MCP tool result, a saved evaluation-run artifact. At that boundary, `EvaluationResult.model_dump()` / `.model_dump_json()` produce the JSON representation directly from the domain object — there is no intermediate hand-built dict, and no path where a dict is built first and then wrapped in Pydantic after the fact (the anti-pattern explicitly named in the task: `evaluation → dict → JSON → Pydantic`). The direction is always `evaluation → Pydantic → (Python callers) or (JSON at a boundary)`.

---

## 9. Non-goals

This design does **not**:
- introduce an `EvaluationEngine`, `Repository`, `Service`, `Mapper`, or `Factory` class;
- convert the whole RAG pipeline (`retrieval.py`, `reranker.py`, `planner.py`, `subjects.py`, `judges.py`) to Pydantic — only `eval.py`'s *result* is modeled;
- change retrieval, reranking, planning, or judging behavior;
- change the security model — access control stays inside `retrieval.access_filter`/`knn_search`; `SecurityAudit` only *reports* what that enforcement already guarantees;
- change the five evaluation configurations, the call-sharing rules, or `MIN_RERANK_SCORE`/`RERANK_STATIC_TOP_K`/`CANDIDATE_POOL_SIZE`/`BASELINE_TOP_K`;
- build a UI, API, or MCP server now — those are named only as reasons the contract needs to be explicit, not as work items here.

---

## 10. Implementation impact

### Where exactly the domain-contract boundary begins

**Answer: at `hits_to_candidates` — the first point raw OpenSearch data becomes a domain object — and it does not end until `report()`, which only ever reads.** Everything in between either *constructs* a model as its main job, or *operates on* already-typed models while remaining a plain, pure, internally-scoped helper — with exactly **one** narrow, explicit exception, discovered by tracing this concretely rather than asserting it: `reranker.rerank_all()` is untouched and its contract is fixed at `list[dict]` in, `list[tuple[dict, float]]` out. Reading its actual body (`f"[{i}] {c['text']}"`) shows it touches exactly **one** field, `text`. So the boundary is not a single clean line — it is crossed once, narrowly, by a tiny adapter around that one call, not by reverting to dicts generally. This is not the rejected `dict → JSON → Pydantic` pattern from §8: that anti-pattern was about the *overall result* round-tripping through a serialization stage before becoming Pydantic; this is a one-field projection around a single fixed, external-shaped function call, immediately converted back.

This finding directly answers the "avoid a blanket rule" instruction: the rule is **not** "every function that used to return a dict now returns a model." It is **"the function whose current job is already ‘assemble the thing this model represents' becomes that model's constructor; every other function keeps its current shape and either doesn't touch models, or reads/writes attributes on models instead of dict keys."**

### Per-function disposition

| Function | Current role | Recommended treatment | Constructs a model? |
|---|---|---|---|
| `hits_to_candidates` | Raw OpenSearch hits → candidate dicts | **Boundary start.** Same signature and loop; builds `Candidate(...)` per hit instead of a dict. | `Candidate` |
| *(new)* `rerank_candidates` | *(doesn't exist today)* | New, small adapter around the untouched `reranker.rerank_all`. Projects `Candidate.text` into the plain-dict shape `rerank_all` needs, calls it, maps the `(dict, score)` results back to the original `Candidate` objects by position/identity. This is the **one** place domain objects are briefly, narrowly converted to dicts and back — nowhere else. | none (pass-through) |
| `annotate_rerank_scores` | Mutates pool dicts in place, keyed by `id(c)` | Becomes a **pure, non-mutating** function: given `candidates: list[Candidate]` and `ranked: list[tuple[Candidate, float]]`, return a **new** `list[Candidate]` with `rerank_score` set (`model_copy(update=...)` for the scored ones). Direct consequence of the immutability decision below — same identity-keyed matching logic, no more in-place mutation. | none (returns updated `Candidate`s) |
| `select_context` | Pure: cuts a ranked list, returns `(selected pairs, text list)` | **Stays a low-level, model-agnostic primitive.** Its job — cut a `list[tuple[T, float]]` by static-k or by threshold — doesn't need to know about `SelectionResult`, `SelectedChunk`, or even that `T` is `Candidate` specifically (it only ever reads `.text`). Keeping it at this level keeps it trivially unit-testable, exactly as it is today. | none |
| `_rank_selected` | `list[(candidate dict, score)]` → `list[dict]` with `final_rank` added | **Evolves into the `SelectedChunk`/`SelectionResult` constructor** (rename suggested: `build_selection_result(selected, texts)`). This is exactly "the function whose job is already to assemble this concept" — it already receives precisely what `SelectionResult` needs (the selected pairs, and `select_context`'s `texts`). It sets `status = "selected" if chunks else "not_found"` and wraps each pair in `SelectedChunk(candidate=c, final_rank=i)`. | `SelectedChunk`, `SelectionResult` |
| `audience_violation` | Pure predicate → `(bool, list[str])` | Becomes the `SecurityAudit` constructor (rename suggested: `audit_security`). Same logic, same one caller pattern, now returns `SecurityAudit(...)` instead of a tuple. | `SecurityAudit` |
| `score_answer` | Branches on `expect_refusal`, returns one of two dict shapes | Becomes the discriminated-union constructor. Same branch, same call sites; returns `RefusalEvaluation(kind="refusal", ...)` or `ContentEvaluation(kind="content", ...)`. | `ContentEvaluation` \| `RefusalEvaluation` |
| `_retrieval_info` | Builds the retrieval dict, **including** `selected` (conflating two concepts) | **Splits.** Once `SelectionResult` is built separately (by `_rank_selected`'s successor), this function no longer needs a `selected` parameter at all — it gets *simpler*, not just retyped: `build_retrieval_result(role, subjects_applied, top_k_requested, pool) -> RetrievalResult`, internally calling `audit_security(pool, role)`. | `RetrievalResult` |
| `run_config` | `(q, contexts, retrieval_info: dict)` → result dict | **Signature changes, not just return type** — and this is deliberate, not incidental: it becomes `(name, q, retrieval: RetrievalResult, selection: SelectionResult) -> ConfigurationResult`. `name` is added because nothing today carries a config's own name *into* its result (only the caller's dict key knows it — see "configuration identity," §6); `contexts` is dropped in favor of reading `selection.context_texts`; `n_chunks` is dropped entirely (computed property, §6/§2). | `ConfigurationResult` |
| `evaluate_question` | Orchestrates one question's 5 configs, returns a dict | **Stays the per-question orchestrator, same call-sharing rules, same order of operations** — only its internal glue changes (calls the model-constructing functions above instead of building dict literals), and its return type becomes `QuestionResult`. | `QuestionResult` |
| `summarize` | Aggregates dicts across questions into a dict | **Stays a plain aggregation function** (not a method on `EvaluationResult` — §6 already decided summary is computed once and stored, not lazily derived). Reads `configuration_result.n_chunks` (now correctly `0` for `not_found` rows — this is where item 2's fix actually takes effect), checks `evaluation.kind` instead of `"refusal_ok" in metrics`, reads `.retrieval.security.violation`. Builds `ConfigSummary(...)` per config name. | `ConfigSummary` |
| `evaluate` | Assembles the whole result dict | **Stays the single top-level constructor**, exactly matching its current role (it's already the one place all three top-level pieces meet). Builds `EvaluationMetadata(...)`, collects `dict[str, QuestionResult]`, calls `summarize()`, returns `EvaluationResult(...)`. | `EvaluationResult` |
| `report` | Reads the result dict, prints a table | **Unchanged role, no model construction at all.** Only its attribute-vs-key access syntax changes (`results.summary[name].n_chunks_avg` instead of `results["summary"][name]["n_chunks_avg"]`). This is the function §8 already describes as an in-process consumer. | none |

`load_questions()` and `main()` are unaffected in role: question *input* records stay plain dicts (this design models `eval.py`'s *result*, not its input — see §1), and `main()` still just wires `opensearch_client()` → `load_questions()` → `evaluate()` → `report()` together.

### A concrete simplification found during this review (recommended, not required)

Today, baseline/filter-only build their `selected` list **inline** in `evaluate_question` (`[{**c, "final_rank": c["vector_rank"]} for c in pool]`), bypassing `select_context`/`_rank_selected` entirely, because there is no rerank score to cut on. This is a real asymmetry: three configs go through the cut pipeline, two don't. Recommendation for the implementation task: give `select_context` a third mode, e.g. `"all"`, that keeps every candidate in its existing (vector) order with `final_rank == vector_rank` — so **all five configs** build their `SelectionResult` through the identical `select_context` → `build_selection_result` path, and the inline special case in `evaluate_question` disappears. This is not required by Pydantic itself; it's a simplification the modeling exercise surfaced. Flagged as a recommendation the implementation task should decide on, not a mandate.

### Files that will need modification (later, separate implementation task)

- `eval.py` — as detailed in the table above.
- `tests/test_eval.py` — every assertion that does dict indexing (`result["configs"]["baseline"]["n_chunks"]`) becomes attribute access (`result.configurations["baseline"].n_chunks`); mechanical, but touches most of the file's 33 tests.
- New file: `models.py` for the Pydantic classes (confirmed location, §11) — not created in this task.

### Files that remain untouched

`client.py`, `judges.py`, `subjects.py`, `planner.py`, `reranker.py`, `retrieval.py`, `config.py`, `create_index.py`, `ingest.py`, `manage.py`. The domain-model layer is a boundary purely inside `eval.py`; nothing upstream needs to know Pydantic exists. `reranker.py` in particular is not modified — the one place its dict contract meets the domain layer is bridged by the small `rerank_candidates` adapter above, inside `eval.py`.

### Resolved design questions

1. **Mutability — resolved: freeze everything, including `Candidate`.** The original draft leaned toward keeping `Candidate` mutable so `annotate_rerank_scores` could set `rerank_score` in place. On review, that's the wrong call: `RetrievalResult`/`EvaluationResult` are meant to be trustworthy, finished snapshots (§6, "Summary"), and a frozen container holding a list of *mutable* `Candidate`s is a leaky guarantee — anyone holding a reference could still change history inside a supposedly-immutable result. Freezing `Candidate` too closes that gap, and it doesn't cost anything: `annotate_rerank_scores`'s identity-keyed matching (`id(c)`) works identically on frozen instances, and rebuilding via `model_copy(update={"rerank_score": score})` is exactly as simple as the current in-place mutation. **Recommendation: every model in the hierarchy is frozen (`model_config = ConfigDict(frozen=True)` or equivalent).**
2. **`RetrievalResult` sharing (configs 4 & 5) — resolved: share the same instance by reference.** With `RetrievalResult` frozen, the only reason *not* to share it (accidental cross-config mutation) no longer exists. Sharing is therefore strictly better: it reflects the true semantic ("this **is** the same retrieval," §6) exactly, and avoids building the candidate list and running `audit_security` twice for what is, in truth, one retrieval. **Recommendation: build one `RetrievalResult` for the filter+rerank pool and reference it from both the static and dynamic `ConfigurationResult`s.**
3. **Discriminated-union mechanics — resolved: yes, add the `kind` tag.** `ContentEvaluation`/`RefusalEvaluation` each get a `kind: Literal["content"]` / `Literal["refusal"]` field, with `ConfigurationResult.evaluation` typed as the discriminated union (`Field(discriminator="kind")` or equivalent). This is the one place a field is added purely for the model's benefit (§6 already named this decision; this confirms it).
4. **`key_facts` on `QuestionResult` — resolved: keep it (item 1 above).**
5. **`n_chunks` as a computed property — resolved: keep it, read-only (item 2 above).**

None of the above changes the model *hierarchy* from §4 — no class is added, removed, or restructured. They resolve *how* the existing classes are constructed and held.

---

## 11. Final Implementation Guidance

This section is the checklist the implementation task must follow. Every point below is a resolved decision, not an option.

- **Location:** the models live in a new `models.py` at the project root. No other name or location was found to have a concrete advantage; it stays technology-neutral in role (the domain contract) even though Pydantic is the implementation technology.
- **Domain-boundary start:** `hits_to_candidates` is the first function to construct a domain model (`Candidate`). Everything downstream either constructs the model matching its existing job (see the table in §10), or operates on already-typed models as a plain function.
- **The one boundary exception:** a new, small `rerank_candidates` adapter wraps the untouched `reranker.rerank_all(list[dict]) -> list[tuple[dict, float]]` contract — projecting only `Candidate.text` out and mapping scores back onto the original `Candidate` objects. This is the sole place domain objects are briefly represented as dicts; `reranker.py` itself is not modified.
- **`Candidate` vs. `SelectedChunk`:** kept distinct. A `Candidate` never has a `final_rank`; a `SelectedChunk` (`{candidate: Candidate, final_rank: int}`) exists only as selection's output. This is enforced by the type, replacing today's convention-only distinction (a dict key that's only sometimes present).
- **`"not found"` semantics:** `SelectionResult.status` is `"not_found"` exactly when `chunks == []`. `context_texts` is still the literal `["not found"]` in that case — the exact string `retrieval.answer()` needs, unchanged. Domain truth (`chunks`, `status`) and prompt presentation (`context_texts`) are two different fields; a consumer counting chunks reads `len(chunks)`, never `len(context_texts)`.
- **`SecurityAudit`:** a standalone model on `RetrievalResult`, built by `audit_security()` (today's `audience_violation`) over the **entire retrieved pool**, not just the selection. It is never folded into `ContentEvaluation`/`RefusalEvaluation` and never averaged as if it were a score — it is a hard invariant, reported, never corrected.
- **Normal vs. refusal evaluation:** a discriminated union, `ContentEvaluation | RefusalEvaluation`, tagged by a new `kind: Literal[...]` field on each, chosen by `score_answer()` based on `expect_refusal`. Not one model with optional fields.
- **`n_chunks`:** a read-only computed property on `ConfigurationResult`, `len(self.selection.chunks)`. Never stored, never passed as a constructor argument. `summarize()`'s `n_chunks_avg` uses this corrected value.
- **`key_facts`:** carried forward onto `QuestionResult`, alongside `id` (also not in today's dict) — both already exist on the input question record; this only decides to keep them on the result.
- **Static/dynamic retrieval sharing:** configs 4 and 5 share **one** `RetrievalResult` instance by reference (safe because it's frozen — see next point) and each get their **own** `SelectionResult`. Build it once; do not rebuild or re-audit the pool for the second config.
- **Immutability:** every model in the hierarchy — including `Candidate` — is frozen. `annotate_rerank_scores`'s successor becomes a pure function returning a new `list[Candidate]` (`model_copy(update=...)`) instead of mutating in place.
- **Serialization boundary:** Pydantic objects are used for their structure and validation *inside* Python throughout `eval.py`, `report()`, and any future in-process consumer. JSON (`model_dump()` / `model_dump_json()`) appears only at an external boundary — a future API response, an MCP tool result, a saved artifact. There is no dict-building stage before the models exist, and no dict-building stage after, before something external needs JSON.
- **Which functions construct models vs. stay plain helpers:** see the table in §10. In one sentence — the function that already assembles a concept becomes that concept's constructor (`hits_to_candidates` → `Candidate`, `_rank_selected` → `SelectedChunk`/`SelectionResult`, `audience_violation` → `SecurityAudit`, `score_answer` → `ContentEvaluation`/`RefusalEvaluation`, `_retrieval_info` → `RetrievalResult`, `run_config` → `ConfigurationResult`, `evaluate_question` → `QuestionResult`, `evaluate` → `EvaluationResult`); `select_context` and `report()` never construct a model and keep their exact current shape.
- **No functional-architecture regressions:** no `EvaluationEngine`, `Repository`, `Service`, `Mapper`, or `Factory` class is introduced anywhere in this list. Every constructor above is a plain function; `eval.py` stays the same kind of module it is today, just returning richer types.

**This document does not implement any of the above.** No Pydantic model has been written; `eval.py` and `tests/test_eval.py` are unmodified. Implementation is a separate, subsequent task.
