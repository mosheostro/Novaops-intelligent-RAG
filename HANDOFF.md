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
  `collection_health(aoss) -> CollectionHealth` is the structured, read-only health use case; `status()`
  prints from it. Its logs carry states and exception types only (no names, endpoint or error text).
- `failures.py` — transport-independent `classify_failure()`: unsupported_role · service_timeout ·
  service_unavailable (incl. resolve_endpoint's SystemExit) · internal. Imported only by the MCP server.
- `mcp_server.py` — MCP adapter, `novaops-knowledge-base` version `SERVER_VERSION` = 0.2.0
  (`--role employee|manager`, required, validated by `access_filter`; `--transport stdio|streamable-http`,
  default stdio; HTTP: `--host` loopback only — 127.0.0.1/localhost/::1 — `--port` default 8000, fixed path
  `/mcp`, stateless JSON responses). Tools `ask_rag`, `health_check`, `get_rag_capabilities`; resource
  `rag://subjects`; no prompts/templates/`get_subjects`. Calls only `ask.ask()` / `manage.collection_health()`;
  returns projections (no chunk text, 1-based source ranks, security violation → answer/sources/judgement
  withheld, count only). Lazy OpenSearch client.
- `mcp_client.py` — MCP client. CLI: `discover` / `health` / `ask QUESTION` with `--url URL` (HTTP) or
  `--role ROLE` (STDIO server started for the command), `--json`. Synchronous functions `describe` /
  `check_health` / `ask` (optional `read_timeout`) for the dashboard. `check_url` → `InvalidServerUrlError`;
  transport failures → `ServerUnavailableError.kind` (unreachable/timeout/not_found/not_mcp/dropped);
  `ToolCallError` = the server's safe message; programming errors are not disguised. Validates nothing of the
  server's domain.
- `models.DEFAULT_CONFIG` = `filter + rerank dynamic` — shared by the Chat page and `ask_rag`.
- `ui/access.py` — UI-only deployment boundary: Streamlit secrets → os.environ bridge (never overwrites;
  shell > .env > secrets) and the mandatory `APP_PASSWORD` gate (fail-closed, hmac.compare_digest,
  session_state). CLI/eval/tests/RAG never need APP_PASSWORD.
- `ui/` — Streamlit dashboard (pages in `ui/app_pages/`, never `ui/pages/`): `streamlit run ui/app.py` from the project root. Pages: Chat (demo role switcher,
  config, optional cutoff date, optional judges, sources + full pipeline trace), Evaluation runs (launcher +
  saved runs), Run detail (summary, questions × configs matrix, per-config drill-down), Infrastructure & Setup,
  MCP server (`app_pages/mcp_page.py`: an MCP client of a separately running server — Connect / Refresh,
  discovery, health, ask_rag; loopback URLs only; 120 s read timeout; degrades without the SDK), About /
  Architecture (read-only visual summary of docs/project-overview.md; static, no backend calls).

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
- MCP: the SDK is optional (`requirements-mcp.txt`, `mcp>=2.3,<3`), never in `requirements.txt`. Only
  `mcp_server.py` / `mcp_client.py` import `mcp`; only `mcp_client.py` imports `anyio`; nothing imports
  `mcp_server`; only `ui/app_pages/mcp_page.py` imports `mcp_client` (`tests/test_mcp_boundary.py`).
- MCP HTTP: an additional transport, not a replacement; loopback only because there is no authentication;
  stateless + JSON responses; one server process per role. The dashboard never starts, stops or supervises
  the MCP server (separate processes). Server version is maintained by hand in `SERVER_VERSION`.
- MCP role = server role fixed at startup, not authentication; no role tool argument, no fallback.
- MCP output never contains infrastructure identifiers (server name is `novaops-knowledge-base`), chunk text,
  vector scores or violating file names. `MAX_QUESTION_CHARS = 2000` is an MCP boundary rule, not an `ask()` rule.
- No MCP server-side timeout (revisit after latency measurements); the dashboard page uses a 120 s client
  read timeout, the CLI the SDK defaults.

## Done
- All modules above implemented; eval.py and the dashboard run against the live collection.
- MCP Stage 1 (STDIO server + minimal client) implemented and validated live (employee and manager, discovery,
  health_check, ask_rag).
- MCP Stage 2 implemented: Streamable HTTP transport, command-based client CLI, dashboard MCP page, server
  version 0.2.0.
- Tests: 595 passing with the MCP SDK installed, `.venv\Scripts\python.exe -m unittest discover -s tests`
  (everything mocked, no AWS — the MCP STDIO/HTTP tests start local server processes with placeholder config on
  loopback; system Python lacks opensearch-py). Without the SDK the MCP test modules are skipped. Logging tests
  assert the WARNING/WARNING defaults.

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
- MCP: the core's security-audit ERROR log names violating files on the server's stderr, and unexpected tool
  errors are logged with tracebacks; `mcp_client.py` forwards the server's stderr to its own. Operator output,
  not protocol output. Live ask_rag latency observed ~10–28 s (not an SLA).
- MCP HTTP (SDK/runtime behavior): stopping the server with Ctrl+Break on Windows shuts uvicorn down
  gracefully but exits with code 3 (uvicorn re-raises the signal); Ctrl+C is caught and exits cleanly. The SDK
  logs "Terminating session: None" at INFO on stderr for every stateless request (no sensitive data). A server
  bound to `127.0.0.1` is not reachable at `http://[::1]:…/mcp` (IPv4-only bind) — use the host it was started
  with.
