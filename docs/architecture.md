# Architecture — current state

**Date:** 2026-10-07 (REST API adapter, §15, and the shared public views; MCP adapter 2026-10-06; the rest unchanged since 2026-09-26)
**Scope:** This document describes the system **as implemented today**. Anything that does not exist yet is marked **FUTURE**.
`docs/architecture-discovery.md` is the original design and discovery record (index inspection, the decisions and their reasoning). `docs/evaluation-domain-model.md` is the design record for `models.py`. `docs/security-concepts.md` is the detailed access-control reference. Where those documents and the code disagree, this document and the code win.

---

## 1. Layers and boundaries

```
                 CURRENT consumers                                                                   FUTURE
   eval.py main() (CLI)   ui/ (Streamlit Dashboard)   mcp_server.py (MCP: STDIO · HTTP)   api_server.py (REST)   other UIs
          │                        │      ▲                   │                            │
          │                        │      └ MCP page ── mcp_client.py ── Streamable HTTP ┘   │  (an MCP client, §14)
          │                        │                          │  public_views.py (§15)     │
          │         ┌──────────────┴──────────────────────────┴────────────────────────────┴─┐
          │         │ ask.ask()   runs.*   manage.collection_health()                         │   application / use-case boundary
          │         └──────────────┬──────────────────────────────────────────────────────────┘
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
- **Consumers** — the CLI (`eval.py main()`: stdout report, optional `--save`), the Dashboard (`ui/`), the MCP server (`mcp_server.py`, §14) and the REST API (`api_server.py`, §15).
  - The Dashboard only calls `ask.ask()` and `runs.*` and renders the returned models. It never calls OpenSearch or Bedrock itself, and it holds no pipeline logic.
  - The MCP server only calls `ask.ask()` and `manage.collection_health()` and returns projections of their results.
  - The REST API calls the same two use cases and returns the same projections; both adapters take them from `public_views.py`.
  - The Dashboard's **MCP server** page is the exception to "calls the use cases in-process": it is an MCP *client* (`mcp_client.py` → Streamable HTTP → a separately running `mcp_server.py`) and never calls the core itself (§10, §14).
  - The Dashboard is not a REST client: it keeps calling the use cases in-process.
  - The architecture stays open for another UI or client. It would call the same use cases; if it leaves the process, it returns the shared public views rather than serializing the domain models (§7). **None exists today.**
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
- In evaluation, a test case whose role is unsupported is still rejected by the same fail-closed `access_filter`, checked first in `eval.evaluate_question`. It is recorded as an `access_violation` for every selected configuration — no planner, embedding, OpenSearch, answer or judge call; the deterministic answer is "Your current role is not supported by this system, so we cannot provide an answer." — and the run continues with the next question. It has no judge score, is excluded from every average (including `refusal_ok`), and is counted in `ConfigSummary.access_violations`. This is an **access denial (the boundary held)**, not a security leak: it never sets `SecurityAudit.violation` and never counts toward `security_violations`.
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
- The same models serve the CLI report, the Dashboard renderers and the tests. The adapters that leave the process — MCP (§14) and the REST API (§15) — never serialize them: they return the explicit projections in `public_views.py`. An earlier version of this document said a future API would serialize the models unchanged; that was rejected, because `AskResult` carries chunk text, vector scores and the sources a failed security audit flagged.
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
- Deferred until a second reason appears, e.g. an API consumer that must not import the evaluation module. The REST API did not create one: like the MCP server it calls `ask.ask()` and imports `eval` only through it.

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
  - Links are never clickable in model/user text: `ui/components/safe_markdown.neutralize_links` (applied to the answer, judge reasons and the echoed question) keeps a link's label, an image's alt text, and shows bare URLs / angle-bracket links / e-mails as code — relative `.md`, internal, localhost, `file://` and external links alike (Option A). Presentation only; stored answers are unchanged.
  - Sources show chunk text as plain text in a bounded, scrollable box (never as markdown, so a chunk starting with `# Title` cannot become a heading); every answer shows an access badge (`access ok` / `access violation`).
  - Refusal presentation: Chat shows "Expected: none — custom question · Detected (refusal judge): Refusal: Yes / No" (never Refusal OK). In runs, expected-refusal cases show *Expected: refusal · Actual (refusal judge): refused / did not refuse · Refusal OK ✓/✗ · content judges skipped*; answerable cases show *Expected: answer · Refusal: not judged*. The question matrix has an *Expected* column. Presentation only — no score is invented.
- **About / Architecture** — a read-only page that presents `docs/project-overview.md` visually (Mermaid diagrams via `st.mermaid_chart`, sources in `ui/components/architecture_diagrams.py`). Static content only: no backend call, no run data, no session state. Help covers how to use the app; this page covers what the system is and why.
- **MCP server** — an MCP client/demo surface (`ui/app_pages/mcp_page.py`, named so it cannot shadow the `mcp` package) for a separately running MCP server; it never starts, stops or supervises one.
  - It talks to the server only through `mcp_client`'s synchronous functions (`describe`, `check_health`, `ask`) with a 120 s read timeout, and imports neither the MCP SDK, `anyio`, `mcp_server` nor the RAG core.
  - Nothing is called when the page opens; **Connect / Refresh** runs discovery and keeps it in session state. The URL must be loopback (`127.0.0.1`, `localhost`, `::1`), checked on the parsed host.
  - Shows the server's identity, transport, role (with a note when it differs from the sidebar role, which does not control it), tools, resources, subjects and capabilities; an explicit health check; and `ask_rag` with configurations taken from the server's capabilities. A security violation shows only the audit; `not_found` is a normal result; the raw MCP response is in an expander.
  - Errors: an unavailable server is a warning with the start command, a tool error shows the server's safe message, anything else a generic message (details to the log). Without the optional SDK the page explains how to install it; the rest of the dashboard is unaffected.
- **API & MCP Help** — a static manual for the two external interfaces (`ui/app_pages/api_mcp_help.py`): how to start the REST API and the MCP server per role (REST 8001/8002, MCP 8000/8010), try them with curl, `mcp_client.py` or MCP Inspector, and where the authoritative contracts live (`/docs`, `/openapi.json`, `tools/list`). Documentation only: it imports only Streamlit, makes no HTTP or MCP call, starts no process and holds no session state. `tests/test_api_mcp_help_page.py` checks what it shows against the real contracts — REST paths against the OpenAPI document, MCP names against the contract snapshot, every command against the real argument parser and every URL against the port that command uses.
- **Help** — a sidebar expander on every page: what the dashboard is, Chat vs runs, the five configurations, cutoff, judges, Refusal OK, sources/trace, runs, and the Bedrock cost warning.
- **Evaluation runs** — the experiment launcher (§13) and a saved-runs table (started, question ids, number of configurations, cutoff, status).
- **Run detail** —
  - run metadata (question count, baseline k, pool size, static k, dynamic threshold);
  - the run's configurations and cutoff (with the cutoff caveat), then a per-configuration summary as neutral measurements — no best/winner highlighting; security violations are flagged in red as invariant failures;
  - a questions × configurations matrix per metric, over the configurations that ran;
  - a per-question drill-down (audience, expected refusal, key facts, planned subjects, and one tab per configuration with the same answer, judge, sources and trace components as Chat).
- The Dashboard does **not** read application log files (`logs/eval.log`). The only log it shows is the tail of a run's own captured output (`runs/<id>.log`), and only while the run is active or after it failed.

---

### Deployment boundary (`ui/access.py`, UI only)

- **Secrets bridge.** `ui/app.py`, before importing `config`, loads the local `.env` and copies the `config.py` variables (six required + `OPENSEARCH_AWS_*` + `OPENSEARCH_ENDPOINT`) from `st.secrets` into `os.environ` only where the environment has no non-blank value — precedence shell > `.env` > Streamlit secrets. Only names are ever reported, never values. `config.py` remains Streamlit-free and unchanged. A side effect: the evaluation subprocess inherits the bridged variables, so launched runs work on Cloud too.
- **Password gate.** `APP_PASSWORD` (environment/`.env` first, then `st.secrets`) is mandatory for every UI run, locally and on Streamlit Community Cloud. Missing, empty or whitespace-only → a clear configuration error and `st.stop()`: no passwordless mode, no environment-based bypass. Otherwise a login screen (`NovaOps Intelligent RAG`, password field, *Sign in*); the input is compared with `hmac.compare_digest`; success sets `st.session_state["authenticated"]`; a wrong password shows only "Incorrect password.". The gate runs before `config`, the RAG modules or the page navigation are imported or rendered. `APP_PASSWORD` is never copied into `os.environ`, logged or displayed.
- **Lifecycle (`ui/app.py`, every run).** Gate → `import config` (a `ConfigError` becomes a safe *Configuration error* naming only the missing variables, no traceback, no values) → shared sidebar (Role radio, so `st.session_state["role"]` exists, and Help) → `st.navigation` → page. Page scripts live in `ui/app_pages/`, deliberately **not** `ui/pages/`: a `pages/` folder next to the entry script enables Streamlit's legacy auto-discovered pages, which Streamlit falls back to whenever a run stops before `st.navigation` (the login screen) — it then lists them and runs a page file on its own, bypassing the gate, `config` and the sidebar. A test forbids `ui/pages/`.
- **Scope.** Basic shared-password demo protection — not user authentication, authorization, OAuth/OIDC or per-user identity. The Employee/Manager role remains a demo retrieval-audience selector. `eval.py`, the tests and the RAG/application modules never read `APP_PASSWORD`.

---

## 11. Logging

**Implemented.**
- **Configuration** — `logging_setup.configure_logging(console_level=WARNING, file_level=WARNING, log_file=logs/eval.log)`:
  - attaches a stderr console handler and a `RotatingFileHandler` (1 MB × 3 backups, UTF-8) to the root logger, whose level is DEBUG so the handlers do the filtering;
  - is idempotent via a marker on its own handlers;
  - pins `boto3`, `botocore`, `urllib3` and `opensearch` to WARNING.
  It is called **only** from `eval.py main()`; importing any module never configures logging.
- **Logger hierarchy** — every module uses `logging.getLogger(__name__)`: `eval`, `ask`, `retrieval`, `planner`, `reranker`, `client`, `config`, `mcp_server`, `api_server`, `public_views`, `ui.app_pages.*`. There is no custom hierarchy.
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

---

## 14. MCP adapter

Stage 1 added the server over STDIO and a minimal client; Stage 2 added Streamable HTTP as a second transport, the command-based client and the dashboard's MCP page. The server, its surface and its projections are the same on both transports.

```
MCP clients: mcp_client.py CLI · Dashboard MCP page (via mcp_client) · MCP Inspector · Claude Code · …
        │  STDIO: JSON-RPC on stdin/stdout, logs on stderr — the client starts the server
        │  Streamable HTTP: POST http://127.0.0.1:<port>/mcp — the server runs on its own (loopback only)
        ▼
mcp_server.py --role employee|manager [--transport stdio|streamable-http]
        │                                    transport adapter: schemas, projections, error mapping
        │            │
        │            └── failures.py         classify_failure(): transport-independent failure categories
        ▼
ask.ask()  ·  manage.collection_health()      application use cases (unchanged by MCP)
```

- **Surface.** Tools `ask_rag`, `health_check`, `get_rag_capabilities`; resource `rag://subjects` (`application/json`). No `get_subjects` tool, prompts or resource templates. The server announces itself as `novaops-knowledge-base`, a public name that is deliberately not an infrastructure identifier, version `SERVER_VERSION` = `0.2.0` — the server implementation's version, bumped by hand, independent of the capabilities `contract_version` (1) and of the MCP protocol version.
- **Subjects in two places.** `get_rag_capabilities` includes the subject vocabulary (and `subjects_resource`, pointing to `rag://subjects`) so that tools-only clients see it; the resource is the read-only vocabulary for clients that read resources. Subjects are not an `ask_rag` input — the planner chooses them. Both come from `subjects.SUBJECTS`, so they cannot drift.
- **Transports.** `--transport stdio` (default) or `streamable-http`; the same `build_server(role)` serves both.
  - Streamable HTTP: `stateless_http=True`, `json_response=True`, fixed path `/mcp`, `--host` (default `127.0.0.1`) and `--port` (default 8000). Only `127.0.0.1`, `localhost` and `::1` are accepted (exit 2 otherwise) — exactly the hosts for which the SDK enables its DNS-rebinding protection (a foreign `Host` gets 421, a foreign `Origin` 403). There is no authentication, so remote binding is refused rather than configurable. One process per role: every HTTP caller gets that server's role.
  - Tool failures are the same JSON-RPC results with `isError` on both transports (HTTP 200); nothing is mapped to HTTP status codes.
- **Role.** `--role` is required and validated at startup by `retrieval.access_filter()`; an unsupported role exits (code 2) before anything is served. The role is fixed for the process and is not a tool argument — a server role, not authentication or client identity.
- **`ask_rag`.** Arguments: `question` (whitespace-stripped, 1–2000 characters — `MAX_QUESTION_CHARS`, an adapter boundary guard shared with the REST API rather than an `ask()` rule), `config` (`ConfigName`, default `models.DEFAULT_CONFIG` = `filter + rerank dynamic`, shared with the Chat page), `judge` (default `false`), `updated_on_or_after` (optional ISO date). Invalid input is rejected by the SDK's schema validation before the use case runs.
- **Response projection (`AskRagResult`, in `public_views.py`, shared with the REST API).** The answer, `config`, `role`, `status` (`selected` / `not_found`), `planned_subjects`, `cutoff`, `retrieval.candidates_considered`, `sources` (metadata only; `rank` is **1-based**, derived from the 0-based domain `final_rank`), `security_audit` (`violation`, `violating_source_count`, `explanation`) and `judgement`. Never chunk text, vector scores, `top_k_requested` or the question.
- **Security violation.** When `SecurityAudit.violation` is true the projection withholds the answer (fixed `WITHHELD_ANSWER`), the sources (`[]`) and the judgement (`null`), and reports only the count and a fixed explanation. The domain `SecurityAudit` keeps the file names internally. Judges requested for such a request have already run inside `ask()`.
- **Health (`HealthResult`).** `ready` (ACTIVE and index present and chunk_count > 0), `collection_state` (control-plane status or `MISSING`), `index_present`, `chunk_count`, `data_plane_reachable` (`null` when not checked). An allow-list over `manage.CollectionHealth`: the endpoint and error text stay with the CLI. A missing, non-active or unreachable collection is a normal result.
- **Failures.** `failures.classify_failure()` → `unsupported_role` · `service_timeout` (checked first) · `service_unavailable` (OpenSearch/botocore errors and the `SystemExit` that endpoint resolution raises) · `internal`. The MCP layer turns the first three into fixed `ToolError` messages and lets `internal` reach the SDK's generic error, so no exception text reaches the client. Business outcomes (`not_found`, a role-filtered answer, a violation) are results, not errors. The REST API maps the same categories to HTTP status codes (§15).
- **Lifecycle.** No infrastructure access at startup or for capabilities/subjects. The OpenSearch client for `ask_rag` is created lazily on first use and cached only after success. Synchronous tools run on SDK worker threads; there is no server-side timeout, and a cancelled request's work finishes in its thread. Ctrl+C stops a manually started server quietly.
- **Logging.** The SDK logs to stderr; over STDIO stdout is protocol only (over HTTP, uvicorn's access log goes to stdout). The health logs carry states and exception types, not names or error text; the request log carries the configuration, role and chunk count, never the question or answer.
- **Dependencies.** The SDK is optional (`requirements-mcp.txt`: `mcp>=2.3,<3`); `requirements.txt` and the dashboard deployment do not include it. Only `mcp_server.py` and `mcp_client.py` import `mcp`; only `mcp_client.py` imports `anyio`; nothing imports `mcp_server`; only `ui/app_pages/mcp_page.py` imports `mcp_client`; `public_views.py` imports no transport package and only the two adapters import it. Enforced by `tests/test_mcp_boundary.py`; `tests/test_mcp_contract.py` pins the published MCP contract against a recorded snapshot.
- **Client (`mcp_client.py`).** Imports no project module and validates nothing of the server's domain; it passes the role through and shows what the server returns.
  - Connections: `connect(role)` starts a STDIO server; `connect_http(url, read_timeout=None)` connects to a running one — by default with the SDK's own HTTP client and timeouts, or with only the read timeout replaced. Kept separate on purpose.
  - Synchronous functions for non-async callers (the dashboard page): `describe(url)`, `check_health(url)`, `ask(url, question, …)`, each one short HTTP session, plain dicts in and out.
  - Errors: `check_url()` raises `InvalidServerUrlError` before connecting (scheme, host, port, missing path — with the fix). Transport failures become `ServerUnavailableError` with a `kind` — `unreachable`, `timeout`, `not_found` (HTTP 404: wrong path), `not_mcp`, `dropped` — and a message built from fixed wording and the URL's scheme, host, port and path (never credentials, query or exception text). `ToolCallError` carries the server's own safe message. Any other exception is a programming error and is not disguised.
  - CLI: `discover` / `health` / `ask QUESTION [--config] [--judge] [--updated-on-or-after]`, each with `--url URL` (HTTP) or `--role ROLE` (STDIO, a server started for that command) and `--json`. Text output is a view of exactly what the server returned; `discover`'s text also shows the tool and resource descriptions the server publishes, and lists the subjects under `rag://subjects`. Usage errors exit 2, operational errors exit 1 with one line; on a STDIO startup refusal the client prints the server's own reason.
- **Dashboard page.** An MCP client of a separately running server; see §10.
- **Not implemented.** Authentication of MCP callers, remote (non-loopback) binding, TLS, CORS for browser clients, the legacy SSE transport, resumability/session management, server-side timeouts, rate limiting, prompts, further tools or resources.

---

## 15. REST adapter

`api_server.py` is a second transport adapter beside the MCP server: plain HTTP + JSON for any HTTP client, built on FastAPI and uvicorn. It owns routes, request schemas, the HTTP boundary and the error contract — nothing else.

```
HTTP clients: curl · scripts · the OpenAPI page /docs · …
        │  http://127.0.0.1:<port>  (loopback only; default port 8001)
        ▼
api_server.py --role employee|manager [--host] [--port]
        │            transport adapter: request schema, HTTP boundary, problem+json error mapping
        │            ├── public_views.py    the public projections, shared with the MCP server
        │            └── failures.py        classify_failure(), shared with the MCP server
        ▼
ask.ask()  ·  manage.collection_health()      application use cases (unchanged by REST)
```

- **Endpoints.** `/docs` and `/openapi.json` are the authoritative contract; there are exactly six paths.
  - `POST /v1/ask` — `ask.ask()` → `public_views.project_ask_result()` → JSON. Body `AskRequest` (unknown fields rejected): `question` (strict string, stripped, 1–2000 characters, the shared `public_views.Question`), `config` (exact `ConfigName`, default `DEFAULT_CONFIG`), `judge` (strict boolean, default `false`), `updated_on_or_after` (`null` or exactly `YYYY-MM-DD`; a future date is valid and simply narrows retrieval). The response is `AskRagResult`, the same projection MCP returns. `not_found` and a failed security audit (answer, sources and judgement withheld) are normal 200 results.
  - `GET /v1/health` — **readiness**: `manage.collection_health(manage.aoss_client())` → `public_views.project_health()`. 200 when `ready`, 503 with the same `HealthResult` body when not. The projection alone decides readiness.
  - `GET /healthz` — **liveness**: the process is up. No backend call.
  - `GET /v1/info` — `{name: "novaops-knowledge-base", version, api_version: "v1", role}`. `API_SERVER_VERSION` (0.1.0) is the REST server's own version, independent of the MCP server's.
  - `GET /v1/capabilities` — the configurations (`public_views.configuration_capabilities()`, shared with MCP), the default, judging, security behaviour and request limits. The same for every role; no MCP concepts (`contract_version`, `subjects_resource`) — the `/v1` path versions the API.
  - `GET /v1/subjects` — `{subjects: [...]}` from `subjects.SUBJECTS`.
- **Role.** `--role` is required and validated at startup by `retrieval.access_filter()` (exit 2 otherwise). It is fixed for the process and is not part of any request: a body with `role` is rejected (422, located at `["body", "role"]`). One process per role.
- **HTTP boundary.** No authentication, so: `--host` accepts only `127.0.0.1`, `localhost` or `::1` (exit 2 otherwise); a middleware rejects a `Host` header that does not name a loopback address (400, which defeats DNS rebinding) and any POST/PUT/PATCH whose `Content-Type` is not `application/json`, including a missing one (415, checked before routing). There is no CORS, so a browser cannot send a JSON body cross-site: the preflight fails. There is deliberately no `Origin` check — with JSON-only bodies and no CORS it would block nothing more, and non-browser clients can send any `Origin`.
- **Errors.** One RFC 9457 `application/problem+json` shape everywhere: `type` (`urn:novaops:problem:<code>`), `title`, `status`, `detail`, plus `errors` (`location`, `message`, `type`) for validation. Fixed wording; never the submitted values or an exception's message (a validation location may name an unknown field). Validation 422; media type 415; unknown path 404; wrong method 405 (with `Allow`); foreign `Host` 400. Use-case failures go through `run_use_case()`, which catches `Exception` **and** `SystemExit` and applies `classify_failure()`: `service_unavailable` (including the `SystemExit` raised by endpoint resolution) 503, `service_timeout` 504, `unsupported_role` 500 (the role is validated at startup, so this is a server fault), anything else 500 `internal-error` with the traceback in the server log only. A failure ends one request, never the server. OpenAPI documents the errors as `Problem`, replacing FastAPI's default validation-error schema.
- **Lifecycle.** No backend access at startup or for liveness and metadata. The OpenSearch client for `/v1/ask` is created lazily on first use (a small lock-protected getter, independent of the MCP one) and cached only after success. Health creates the control-plane client per call, like MCP. Routes are synchronous and run on the framework's worker threads; one process, no workers; no server-side timeout.
- **Logging.** Category and exception type for handled failures; never questions, answers or exception text. The REST server does not call `configure_logging()`: its warnings reach stderr through Python's last-resort handler; uvicorn's access log shows method, path and status.
- **Dependencies.** Optional `requirements-api.txt` (`fastapi`, `uvicorn`); not in `requirements.txt` or the dashboard deployment. Only `api_server.py` imports FastAPI, Starlette or uvicorn; nothing imports `api_server`; it imports neither MCP nor Streamlit/UI code, and reaches the core only through `ask`, `manage`, `public_views` and `subjects` (`tests/test_api_boundary.py`).
- **Tests.** In-process (`tests/test_api_server.py`, `test_api_ask.py`, `test_api_health.py`, `test_api_metadata.py`, all AWS mocked); real processes on loopback with AWS calls refused locally (`tests/test_api_http.py`, always run); and opt-in live tests against the real backend in the same module (`NOVAOPS_LIVE_TESTS=1`), the only tests that call AWS.
- **Not implemented.** Authentication, remote binding, TLS, CORS, rate limiting, server-side timeouts, request cancellation of model calls already under way.
