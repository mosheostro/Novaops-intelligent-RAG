# HANDOFF — NovaOps Intelligent RAG

## Architecture
Corpus (`data/handbook` = `audience: all`, `data/manager_playbook` = `audience: manager`; markdown) → chunking
250/50 words → Titan v2 embeddings → `novaops-kb` index in OpenSearch Serverless (k-NN). Query flow: planner
(LLM picks subjects) → k-NN with pre-filter (mandatory access + optional subjects + optional recency cutoff) →
listwise reranker → chunk selection → Nova answer via Bedrock Converse → LLM judges.
Current architecture: `docs/architecture.md` (wins over the older design records
`docs/architecture-discovery.md` and `docs/evaluation-domain-model.md`).

## Modules
- `config.py` — loads `.env`; all variables are required (no defaults).
- `client.py` — sole owner of the Bedrock runtime client (`bedrock`, `embed_text()`) and the OpenSearch data plane.
- `subjects.py` / `subjects.json` — subjects vocabulary, tagger, per-article tag cache.
- `create_index.py` / `ingest.py` — non-destructive: check-only by default, writes only into an empty index.
- `retrieval.py` — k-NN + filters: audience (hard security, fail-closed), subjects (soft, fail-open),
  recency cutoff (`last_updated >= cutoff`, off unless given).
- `planner.py` — LLM subjects planner (forced tool call).
- `reranker.py` — listwise rerank; ranks only (the static/dynamic cuts are in `eval.py`).
- `judges.py` — 4 LLM judges: faithfulness, context_relevance, completeness, refusal (boolean, forced tool).
- `models.py` — frozen Pydantic v2 domain models; incl. `AskResult`, `LiveJudgement`, `RetrievalResult.cutoff`.
- `eval.py` — experiment = questions × configurations (any of the 5) × optional cutoff; planner at most once per
  question, rerank once per pool (static+dynamic share one). `select_questions`, `estimate_calls`. CLI `--ids`,
  `--config` (repeatable), `--cutoff`, `--save`, `--run-id`, `--questions PATH` (no flags = all, print only).
- `ask.py` — one custom question through ONE config, optional `cutoff`, optional live judges
  (faithfulness + context_relevance + refusal detection `LiveJudgement.refused` + completeness vs. retrieved
  context via `judges.context_completeness`, skipped when no selected chunks or refused; no refusal_ok). Reuses eval.py's pipeline helpers and judges.refusal.
- `runs.py` — saved `EvaluationResult` artifacts under `runs/` (gitignored); launches `eval.py --save` as a
  subprocess, one at a time per server process; `delete_run(id)` removes one run's .json/.log (listed ids only).
- `logging_setup.py` — centralized logging; `configure_logging()` is called only from `eval.py main()`.
- `manage.py` — `status` / `down` (typed REMOVE); the only exception: OpenSearch control-plane client.
- `ui/access.py` — UI-only deployment boundary: Streamlit secrets → os.environ bridge (never overwrites;
  shell > .env > secrets) and the mandatory `APP_PASSWORD` gate (fail-closed, hmac.compare_digest,
  session_state). CLI/eval/tests/RAG never need APP_PASSWORD.
- `ui/` — Streamlit dashboard (pages in `ui/app_pages/`, never `ui/pages/`): `streamlit run ui/app.py` from the project root. Pages: Chat (demo role switcher,
  config, optional cutoff date, optional judges, sources + full pipeline trace), Evaluation runs (launcher +
  saved runs), Run detail (summary, questions × configs matrix, per-config drill-down), About / Architecture
  (read-only visual summary of docs/project-overview.md; static, no backend calls).

## Decisions
- Bedrock boundary: no other module creates `boto3.client("bedrock-runtime")`.
- Structured output only via forced tool call; temperature 0.0 for judges.
- Selection: static top-3; dynamic — score ≥ 0.6, no fallback to top-1; nothing passing → zero chunks,
  `status="not_found"`, and the prompt gets "not found" (presentation only, not a document).
- Access filtering is mandatory everywhere and never an experiment variable; `SecurityAudit` covers the whole pool.
- Recency: one cutoff date, `last_updated >= cutoff`, independent of the configuration; evaluation runs don't use it.
- Refusal is scored by an LLM judge over the whole answer. `expect_refusal` = dataset expectation,
  `refusal_ok` = observed behavior.
- `data/eval_questions.jsonl` is the only preset dataset; one record = one test case (question + audience +
  expectations for that role). `scenario` is display/filter metadata only — the evaluator never reads it.
- No global audience override for eval runs; no access-filter control anywhere. No best/winner highlighting.
- Logs never contain prompts, answers, chunk text, key_facts, or secrets.
- Do not delete / recreate / reindex the `novaops-kb` index without an explicit request.
- `.env` and `.streamlit/secrets.toml` are not committed; the PAT from the original README is never reproduced anywhere.
- The dashboard never runs without `APP_PASSWORD` (local `.env` or Cloud secrets); it is demo protection only.

## Done
- All modules above implemented; eval.py and the dashboard run against the live collection.
- Tests: 383, `.venv\Scripts\python.exe -m unittest discover -s tests` (everything mocked, no network;
  system Python lacks opensearch-py). Logging tests assert the WARNING/WARNING defaults.
- Last commit: `0e70db3 handoff - 1`. The UI layer, the cutoff and the doc updates are NOT committed yet.

## Known issues / open items
- ACCESS_REVIEW (expect_refusal=true) → refusal_ok=False in all configs: the model answers from handbook
  content. Evaluation/dataset question, not a UI or security bug.
- Judge unit tests mock the model — they verify the wiring, not semantic accuracy.
- The refusal judge costs +1 Bedrock call per refusal question × config.
- `ask.py` imports pipeline helpers (incl. private `_select_all`) from `eval.py`; a small shared
  `pipeline.py` is the justified follow-up (docs/architecture.md §8) — deferred, not required for correctness.
- Logging gaps: the Streamlit process does not call `configure_logging()`; no log viewer beyond a run's
  output tail; no per-module log-level controls (docs/architecture.md §11).
- One-run-at-a-time is per Streamlit server process only; a server restart during a run shows it as
  "failed" until its JSON appears.
- `CLAUDE.md`'s module list and "design is in docs/architecture-discovery.md" predate `ask.py`/`runs.py`/`ui/`
  and `docs/architecture.md`.
