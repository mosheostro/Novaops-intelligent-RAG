# Architecture — current state

**Date:** 2026-09-26
**Scope:** This document describes the system **as implemented today**. Anything that does not exist yet is marked **FUTURE**.
`docs/architecture-discovery.md` is the original design and discovery record (index inspection, the decisions and their reasoning). `docs/evaluation-domain-model.md` is the design record for `models.py`. `docs/security-concepts.md` is the detailed access-control reference. Where those documents and the code disagree, this document and the code win.

---

## 1. Layers and boundaries

```
                 CURRENT consumers                         FUTURE consumers (not implemented)
   eval.py main() (CLI)      ui/ (Streamlit Dashboard)      HTTP API · MCP server/tools · other AI clients
          │                        │
          │         ┌──────────────┴───────────────┐
          │         │ ask.ask()        runs.*       │   application / use-case boundary
          │         └──────────────┬───────────────┘
          ▼                        ▼
   eval.evaluate() / evaluate_question()                 evaluation runner + shared pipeline steps
          │
          ▼
   models.py  ── frozen Pydantic domain models: the contract every consumer reads
          ▲
   RAG core:  retrieval.py · planner.py · reranker.py · judges.py · subjects.py
          ▲
   infrastructure:  client.py (Bedrock runtime + OpenSearch data plane) · config.py · logging_setup.py
```

- **RAG core** — `retrieval.py` covers the filters, k-NN search and answer generation. `planner.py` is the subject planner, `reranker.py` the listwise reranker, `judges.py` the LLM judges, and `subjects.py` the vocabulary and tagger. It has no knowledge of the UI, the CLI or saved runs.
- **Domain models** — `models.py` holds frozen Pydantic v2 models: `Candidate`, `SelectedChunk`, `SecurityAudit`, `RetrievalResult`, `SelectionResult`, `ContentEvaluation` | `RefusalEvaluation`, `ConfigurationResult`, `QuestionResult`, `EvaluationMetadata`, `ConfigSummary`, `EvaluationResult`, `LiveJudgement` and `AskResult`. They are the stable in-process contract between the core/application layer and every consumer. There are no dicts in between; see §7.
- **Application / use-case boundary** — two use cases plus one storage helper:
  - `ask.ask()`: one custom question answered by one configuration.
  - `eval.evaluate()`: one experiment — questions × selected configurations (default all five) × optional cutoff.
  - `runs.py`: saved evaluation artifacts and the run launcher.
- **Consumers** — the CLI (`eval.py main()`: stdout report, optional `--save`) and the Dashboard (`ui/`).
  - The Dashboard only calls `ask.ask()` and `runs.*` and renders the returned models. It never calls OpenSearch or Bedrock itself, and it holds no pipeline logic.
  - The architecture stays open for an HTTP API, an MCP tool layer or another UI. Each would call the same `ask.ask()` / `eval.evaluate()` / `runs.*` and serialize the same models. **None of these exist today.**
- **Bedrock boundary** — `client.py` is the only module that constructs the Bedrock runtime client. `ask.py`, `runs.py` and `ui/` construct none. `manage.py` owns the OpenSearch Serverless control-plane client, a documented exception that does not cover Bedrock.

---

## 2. Pipeline and responsibilities

```
question + audience (+ optional cutoff date)
  → planner                (planner.plan_subjects)          only for configs that use the subject filter
  → access filter          (retrieval.access_filter)        MANDATORY, every path — security
  → subject filter         (retrieval.subject_terms)        optional — quality/relevance, fail-open
  → recency cutoff         (retrieval.recency_range)        optional — quality/retrieval constraint
  → vector retrieval       (retrieval.knn_search)           all filters INSIDE the k-NN query (pre-filter)
  → candidate pool         (eval.hits_to_candidates)        k = 4 or N = 10 Candidates
  → security audit         (eval.audit_security)            audits the WHOLE pool; reports, never corrects
  → reranking              (reranker.rerank_all via eval.rerank_candidates)   configs 3–5 only
  → selection              (eval.select_context / _select_all / build_selection_result)
  → answer generation      (retrieval.answer)               grounded in the selected context only
  → judges                 (judges.*)                       evaluation, never part of answering
```

| Concern | Kind | Where | Behavior |
|---|---|---|---|
| Access filtering | **Security** | `retrieval.access_filter` | Mandatory and never user-selectable. Fails closed (§3). |
| Subject filtering | Quality / relevance | `planner.py` + `retrieval.subject_terms` | Fails open: a `[]` plan means no subject clause. |
| Recency cutoff | Quality / retrieval constraint | `retrieval.recency_range` | One date, `last_updated >= cutoff` (§4). Off by default. |
| Retrieval | Recall | `retrieval.knn_search` | Filters go inside the `knn` block, never `post_filter`. |
| Reranking | Precision / order | `reranker.rerank_all` | Only ranks; it never decides how many chunks survive. Unscored candidates get 0.0. |
| Selection | Context-size decision | `eval.select_context` | Static top-3, or dynamic `score >= 0.6` with no top-1 fallback (§5). |
| Answer generation | Synthesis | `retrieval.answer` | Uses only the provided context; states plainly when the answer is not there. |
| Evaluation | Measurement | `judges.py`, `eval.score_answer`, `eval.summarize` | Separate from answering. Scores are never fed back into the pipeline. |

---

## 3. Security invariant

- `SUPPORTED_AUDIENCES = {"employee", "manager"}` in `retrieval.py` is the only definition of the supported audiences.
- `employee` may retrieve only chunks with `audience: "all"`.
- `manager` has no audience restriction within the current corpus (both `all` and `manager` chunks).
- Any other value — an unknown role, a typo, a different casing, an empty string — raises `UnsupportedAudienceError`. The error comes before any clause is built, any embedding is made or OpenSearch is contacted. `ask.ask()` additionally validates the role before the planner runs, so a rejected role costs no Bedrock call.
- Access filtering is **not** an experiment variable. It is applied in all five configurations, in `ask.ask()`, and whether or not a recency cutoff or subject filter is active. Soft filters can only narrow an already-authorized pool.
- `SecurityAudit` audits the **full retrieved candidate pool**, not only the selected chunks. A violation is an invariant failure — an architectural defect. It is logged at ERROR and surfaced in red in the Dashboard. It is **not** a quality score and is never averaged into one; `ConfigSummary.security_violations` is a count.
- The Dashboard's role switcher is a **demo control, not authentication**. It chooses which supported audience a session uses. Real authentication is FUTURE.

---

## 4. Subject filter and recency cutoff

**Subject filter.** It is a quality/relevance filter. The planner makes one forced tool call over the fixed `subjects.SUBJECTS` vocabulary; invalid labels are dropped and `[]` means no restriction. `RetrievalResult.subjects_applied` distinguishes three cases:
- `None`: the configuration does not use the filter.
- `[]`: the planner ran and found nothing, so the search ran unfiltered (fail-open).
- a non-empty list: those subjects were applied.

**Recency cutoff (CURRENT, deliberately simple).**
- The user supplies **one** `cutoff` date. Semantics: `last_updated >= cutoff`, **inclusive** of the cutoff date itself.
- `retrieval.recency_range(updated_after)` builds `{"range": {"last_updated": {"gte": "yyyy-MM-dd"}}}` inside the same pre-filter as the access clause.
- `ask.ask(..., cutoff: date | None = None)` converts the date and passes it to `knn_search` for **every** configuration. `None` means no recency constraint.
- The applied value is recorded in `RetrievalResult.cutoff`, which defaults to `None`, so runs saved before the field existed still load.
- The cutoff is **independent of the configuration name**: configuration selects the retrieval/rerank/selection strategy; the cutoff constrains which documents are eligible. They are separate inputs.
- The Dashboard chat exposes it as an optional "Updated on or after" date input, and the pipeline trace shows it.
- Evaluation runs may set one cutoff for the whole experiment (`evaluate(..., cutoff=)`, `--cutoff`); it applies to every selected configuration and is recorded in `EvaluationMetadata.cutoff` and each `RetrievalResult.cutoff`. The dataset's expectations assume the full corpus, so the launcher and the run detail show a caveat: with a cutoff, scores can drop because the evidence was excluded.
- There is no `date_from`/`date_to`, no range and no date abstraction.

Verified live (read-only `count`): employee pool 217 chunks; `>= 2025-04-28` gives 135, and the next day gives 112. The document dated exactly on the cutoff is included.

---

## 5. The five evaluation configurations

| # | Name | Behavior |
|---|---|---|
| 1 | `baseline` | access + vector top-4, no rerank, all 4 used |
| 2 | `filter-only` | access + subject filter + vector top-4, no rerank, all 4 used |
| 3 | `rerank-only` | access + candidate pool 10 + rerank + static top-3 |
| 4 | `filter + rerank static` | access + subject filter + candidate pool 10 + rerank + static top-3 |
| 5 | `filter + rerank dynamic` | access + subject filter + candidate pool 10 + rerank + every candidate with score ≥ 0.6 |

Constants live in `eval.py`: `BASELINE_TOP_K = 4`, `CANDIDATE_POOL_SIZE = 10`, `RERANK_STATIC_TOP_K = 3`, `MIN_RERANK_SCORE = 0.6`. They are recorded per run in `EvaluationMetadata`.

**Dynamic selection never falls back to top-1.** If nothing reaches 0.6:
- `SelectionResult.status = "not_found"` and `chunks = []`, so zero selected chunks and `n_chunks = 0`.
- `context_texts = ["not found"]`. This is **prompt/presentation** input that makes `retrieval.answer()` produce a grounded refusal. It is not a retrieved document, and it is never counted as a chunk.

**Execution model** (`eval.evaluate_question`):
- The planner runs **once per question**; its result is reused by configs 2, 4 and 5.
- k-NN runs once per distinct pool: baseline (k=4), filter-only (k=4, subjects), rerank-only (N=10) and filter+rerank (N=10, subjects).
- Reranking runs **once per unique candidate pool**, i.e. twice per question:
  - the rerank-only pool;
  - the shared filter+rerank pool, whose single reranked list, and single `RetrievalResult`, feeds both the static and the dynamic cut. Static-vs-dynamic therefore differs only by the cut, never by model noise.
- Answers are one per configuration. Judges are three per answerable configuration result, or one refusal judge per refusal-expected one.
- With a configuration subset the same rules hold for what is selected: the planner runs only if a selected configuration uses the subject filter (otherwise `QuestionResult.planned_subjects` is `None`), each pool is retrieved only if a selected configuration needs it, and static + dynamic still share one pool and one rerank. `eval.estimate_calls(questions, configs)` counts calls with exactly these rules; the UI uses it and does not duplicate them.
- `ask.ask()` runs exactly one configuration, so it makes at most one planner call and one rerank call.

---

## 6. Preset vs custom questions

| | Preset (evaluation) | Custom (Dashboard chat) |
|---|---|---|
| Source | `data/eval_questions.jsonl`, one test case per line: `id`, `question`, `audience`, `expect_refusal`, `key_facts`, `report`, `scenario` | Typed by the user |
| Audience | From the record | Chosen explicitly in the sidebar (demo role) |
| Entry point | `eval.evaluate()` (CLI or launcher subprocess) | `ask.ask()` |
| Configurations | The selected subset (default all five) | The one selected |
| Judges | Answerable: faithfulness, context relevance and completeness (against `key_facts`). `expect_refusal`: the refusal judge only, stored as `refusal_ok` | Optional ("Score with judges", +4 calls): faithfulness, context relevance, the **same** `judges.refusal` stored as `LiveJudgement.refused` (detected behavior only; no `refusal_ok` — no expected behavior), and **Completeness (vs. retrieved context)** via `judges.context_completeness(question, contexts, answer)` — skipped (n/a, no call) when there are zero selected chunks or the answer is a refusal. It is a different metric from batch completeness (key facts) and is never mixed with it |
| Result | `QuestionResult` inside `EvaluationResult`, savable as a run | `AskResult`, kept only in the browser session |

A custom question is never written into a question set or a saved run, and the Dashboard does not present it as part of the dataset.

**The preset dataset.**
- `data/eval_questions.jsonl` is the single source of preset evaluation questions; its size is whatever the file holds (nothing assumes a count).
- One record is one **test case**: `audience` is the role it runs as, and `expect_refusal` / `key_facts` are defined for that role. Evaluation always runs a case as its own audience — there is no global audience override, because expectations for another role do not exist in the record. Testing the same question under another role means adding another record with its own id and expectations (none are added today).
- `scenario` — `standard`, `cross_source` (XSRC_SEV_TERM), `access_boundary` (ACCESS_REVIEW: the answer exists but is manager-only), `out_of_corpus` (UNANSWERABLE_AWS) — is **display/filter metadata only**. The evaluator never reads it (tested).
- `report` flags a case for the CLI's detailed printout; the Dashboard ignores it.
- `eval.py --questions PATH` can point the CLI at another file; the Dashboard always uses the canonical one.

**An experiment** = selected test cases × selected configurations × optional cutoff (§13).

---

## 7. Domain model boundary (`models.py`)

- Every model is frozen. The pipeline builds them directly; there is no internal dict stage.
- The one narrow exception is `eval.rerank_candidates`, which adapts to `reranker.rerank_all`'s fixed dict-in/dict-out contract (`{"text": ...}`) and maps the results back by identity.
- JSON appears only at external boundaries: `EvaluationResult.model_dump_json()` for saved runs and `model_validate_json()` to load them.
- The same models serve the CLI report, the Dashboard renderers, the tests, and a FUTURE API or MCP layer, which would serialize them unchanged.
- `ConfigurationResult` (eval) and `AskResult` (chat) share `RetrievalResult` and `SelectionResult`, so the Dashboard renders both with the same components.
- No repository, service, mapper or factory layers exist, and none are needed.

---

## 8. `ask.py` and its dependency on `eval.py`

**Current.**
- `ask.py` imports the pipeline-step helpers from `eval.py`: `hits_to_candidates`, `rerank_candidates`, `attach_rerank_scores`, `select_context`, `build_selection_result`, the private `_select_all`, `build_retrieval_result`, and the constants.
- `ui/components/trace.py` imports the constants and `runs.py` imports `RUNS_DIR` from `eval.py` as well.

**Assessment.**
- It is correct and tested, and it guarantees that chat and evaluation use literally the same steps.
- The dependency direction is semantically inverted: answering a question depends on the *evaluation* module and pulls in its judges and CLI code.
- It also uses one private name (`_select_all`).
- It is **acceptable for now**; nothing is incorrect.

**Justified follow-up, not done.** A small `pipeline.py` would hold only the shared, pure pipeline steps:
- Moves: the four constants, `hits_to_candidates`, `rerank_candidates`, `attach_rerank_scores`, `select_context`, `build_selection_result`, `select_all` (made public), `audit_security` and `build_retrieval_result`.
- Stays in `eval.py`: `evaluate_question`, `evaluate`, `run_config`, `score_answer`, `summarize`, `load_questions`, `report`, `main`, `RUNS_DIR`, `save_result`.
- `ask.py` and `eval.py` would both import from `pipeline.py`.
- No new abstraction, no class, no behavior change.
- Deferred until a second reason appears, e.g. an API consumer that must not import the evaluation module.

---

## 9. Run persistence (`runs/`)

`runs/` holds **saved evaluation run artifacts**. It is not a database, and it is gitignored.

- **Artifact:** `runs/<run_id>.json` is one serialized `EvaluationResult`. `runs/<run_id>.log` is the captured stdout+stderr of a launcher-started run.
- **Creation:** `eval.py [--ids …] [--config …] [--cutoff …] --save [--run-id ID]` writes the JSON after the whole run has finished and printed its report. The default id is `<UTC yyyymmddThhmmssZ>_<question-file stem>`; what ran (question ids, configurations, cutoff) is read from the saved metadata, not the id.
- **Loading:** `runs.load_run(id)` calls `EvaluationResult.model_validate_json`. The detail page caches it by id because artifacts are immutable.
- **Discovery:** `runs.list_runs()` returns the union of the `*.json` and `*.log` file stems, newest first, each with a status (and, once done, its question ids, configurations and cutoff from the saved metadata):
  - `running`: this server process holds a live subprocess for the run.
  - `done`: the JSON exists.
  - `failed`: anything else.
- **Launch:** `runs.launch_run(question_ids, configs, cutoff=None)` starts `python eval.py --ids A,B --config NAME [--config NAME …] [--cutoff YYYY-MM-DD] --save --run-id ID` via `subprocess.Popen`:
  - working directory is the project root;
  - output goes to `runs/<id>.log`;
  - `PYTHONIOENCODING=utf-8` and `PYTHONUNBUFFERED=1` are set.
- **Isolation:** the run is a separate Python process with its own logging configuration. A long run never blocks or shares state with the Streamlit process, and a crash in it cannot take the UI down.
- **One run at a time:** enforced only within one Streamlit server process (`RunAlreadyActiveError`). It does not coordinate with CLI runs or a second server.
- **Terminated before the artifact exists:** no JSON is written, because the write is all-or-nothing at the end. The run shows as `failed`, and the Runs page shows the tail of its log. There are no partial results.
- **Deletion:** `runs.delete_run(id)` removes that run's `.json` and `.log` only; it accepts only ids that `list_runs()` reports (the id can come from a URL) and refuses a running run. The UI offers it on Run detail and for failed runs, behind an explicit confirmation tick; there is no delete-all.
- **Server restart during a run:** the `Popen` handle is lost, so the run shows `failed` until its subprocess (which keeps running) writes the JSON; then it shows `done`.

---

## 10. Dashboard (`ui/`)

The Dashboard is an **evaluation laboratory and presentation layer**: it exposes the pipeline rather than hiding it. Run it with `streamlit run ui/app.py` from the project root; the theme is in `.streamlit/config.toml`.

- **Chat** — inputs are the question, the audience (sidebar), one of the five configurations, an optional cutoff date and an optional judges toggle.
  - Each answer shows the configuration, audience and chunk count, the security status (red banner on violation) and the `not_found` notice.
  - It also shows the answer, the judge scores with reasons, and the selected sources (source, corpus, audience, subjects, last_updated, vector and rerank scores, text).
  - The pipeline trace shows the subject filter state, the cutoff, the pool size, the selection rule, and the **full candidate pool** with vector scores, rerank scores, a selected flag and the final rank.
  - History is per browser session and single-turn: it is never sent to the model.
  - Layout: the controls (configuration, cutoff, judges toggle, **Clear**) stay at the top; only the conversation scrolls, in a fixed-height container that auto-scrolls to the newest message; the input is pinned at the bottom. **Clear** empties this session's conversation only — settings, saved runs and datasets are untouched.
  - Sources show chunk text as plain text in a bounded, scrollable box (never as markdown, so a chunk starting with `# Title` cannot become a heading); every answer shows an access badge (`access ok` / `access violation`).
  - Refusal presentation: Chat shows "Expected: none — custom question · Detected (refusal judge): Refusal: Yes / No" (never Refusal OK). In runs, expected-refusal cases show *Expected: refusal · Actual (refusal judge): refused / did not refuse · Refusal OK ✓/✗ · content judges skipped*; answerable cases show *Expected: answer · Refusal: not judged*. The question matrix has an *Expected* column. Presentation only — no score is invented.
- **Help** — a sidebar expander on every page: what the dashboard is, Chat vs runs, the five configurations, cutoff, judges, Refusal OK, sources/trace, runs, and the Bedrock cost warning.
- **Evaluation runs** — the experiment launcher (§13) and a saved-runs table (started, question ids, number of configurations, cutoff, status).
- **Run detail** —
  - run metadata (question count, baseline k, pool size, static k, dynamic threshold);
  - the run's configurations and cutoff (with the cutoff caveat), then a per-configuration summary as neutral measurements — no best/winner highlighting; security violations are flagged in red as invariant failures;
  - a questions × configurations matrix per metric, over the configurations that ran;
  - a per-question drill-down (audience, expected refusal, key facts, planned subjects, and one tab per configuration with the same answer, judge, sources and trace components as Chat).
- The Dashboard does **not** read application log files (`logs/eval.log`). The only log it shows is the tail of a run's own captured output (`runs/<id>.log`), and only while the run is active or after it failed.

---

## 11. Logging

**Implemented.**
- **Configuration** — `logging_setup.configure_logging(console_level=WARNING, file_level=WARNING, log_file=logs/eval.log)`:
  - attaches a stderr console handler and a `RotatingFileHandler` (1 MB × 3 backups, UTF-8) to the root logger, whose level is DEBUG so the handlers do the filtering;
  - is idempotent via a marker on its own handlers;
  - pins `boto3`, `botocore`, `urllib3` and `opensearch` to WARNING.
  It is called **only** from `eval.py main()`; importing any module never configures logging.
- **Logger hierarchy** — every module uses `logging.getLogger(__name__)`: `eval`, `ask`, `retrieval`, `planner`, `reranker`, `client`, `config`, `ui.pages.*`. There is no custom hierarchy.
- **Storage** —
  - `logs/eval.log` (gitignored; the path is relative to the working directory), written by CLI runs and by launcher subprocesses;
  - `runs/<id>.log`, the full stdout/stderr of a launcher run: the report plus WARNING+ log lines.
- **Sensitive data** — logs carry ids, configuration names, audiences, counts and source file names. They never carry prompts, answers, chunk text, `key_facts` or secrets.
  - Caveat: `logger.exception` records an exception's message and traceback. The chat page logs a failed `ask` this way, while the user sees only the exception type.

**Not implemented (current gaps, stated honestly).**
- **The Streamlit process does not call `configure_logging()`.** Its module WARNING+ records reach stderr only through Python's last-resort handler, and nothing from the UI process goes to `logs/eval.log`.
- There is no log viewer in the Dashboard beyond the run-output tail described above.
- There are no module-specific log-level controls: only the two handler levels (function parameters, not exposed via CLI or UI) and the fixed third-party suppression.

---

## 12. Evaluation semantics and known issues

- **Refusal:**
  - `expect_refusal` is the dataset's **expectation**.
  - The model's **actual behavior** is judged by `judges.refusal(question, answer)`: an LLM judge with a forced boolean tool call at temperature 0.0 that reads the whole answer, not keywords.
  - The judge's verdict is stored as `RefusalEvaluation.refusal_ok`, the **observed** outcome.
  - Content judges are not run for refusal-expected questions.
  - The former keyword heuristic `refused()` no longer exists.
- **Known issue — `ACCESS_REVIEW`** (employee, `expect_refusal: true`): `refusal_ok = False` in all five configurations, because the model answers from handbook content visible to employees. This is an **evaluation/dataset question**: is the expectation right for this corpus, or is it a judging issue? It is not a Dashboard or security bug. Refusal semantics are not changed because of one live score.
- **Judge tests** mock the model: they verify the wiring, not semantic accuracy.
- The **refusal judge** adds one Bedrock call per refusal question and configuration.

---

## 13. Dashboard experiment workflow

```
Questions  (data/eval_questions.jsonl — quick select: All · None · Employee · Manager)
  ☑ SEV_3YR · employee · answer · standard — If I've worked here for 3 years and get lai…
  ☑ ACCESS_REVIEW · employee · refusal · access_boundary — How do I run a formal performan…
  …                         (full question text on hover; audience comes from each test case)
Configurations  (the access filter is always on)
  ☑ baseline — vector top-4            ☐ rerank-only — pool 10 · rerank · top-3   …
Updated on or after (optional)  [2025-04-28]
Run summary: cases (audience · expectation) · configurations · recency · access always on
             · N questions × M configurations = answers · ≈ model calls (eval.estimate_calls)
☐ I understand this run makes paid Bedrock calls        [ Run selected experiments ]
```

- The Dashboard selects a subset of canonical test cases by **id**; the dataset is never copied or changed. `runs.launch_run(ids, configs, cutoff)` → `eval.py --ids … --config … [--cutoff …] --save`. `eval.select_questions` keeps dataset order and rejects an unknown id or an empty selection; `resolve_configs` rejects an unknown or empty configuration selection; argparse rejects a malformed date — all before any logging setup, client or model call.
- The run button stays disabled until at least one case and one configuration are selected and the cost is confirmed; the confirmation resets after each launch.
- Not offered, deliberately: an access-filter control, a run-wide audience override, date ranges, and any best/winner marking.
