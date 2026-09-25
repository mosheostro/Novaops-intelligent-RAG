# HANDOFF — NovaOps Intelligent RAG

## Architecture
Corpus (handbook + eng-wiki, markdown) → chunking 250/50 tokens → Titan v2 embeddings →
`novaops-kb` index in OpenSearch Serverless (k-NN). Query flow: planner (LLM picks subjects) →
k-NN with pre-filter → listwise reranker → chunk selection → Nova answer via Bedrock Converse →
scoring by LLM judges. Details: `docs/architecture-discovery.md`, `docs/evaluation-domain-model.md`.

## Modules
- `config.py` — loads `.env`; all variables are required (no defaults).
- `client.py` — sole owner of the Bedrock runtime client (`bedrock`, `embed_text()`) and the OpenSearch data plane.
- `subjects.py` / `subjects.json` — subjects vocabulary, tagger, per-article tag cache.
- `create_index.py` / `ingest.py` — non-destructive: check-only by default, writes only into an empty index.
- `retrieval.py` — k-NN + filters: audience (hard security, fail-closed), subjects (soft, fail-open), recency (off).
- `planner.py` — LLM subjects planner (forced tool call).
- `reranker.py` — listwise rerank, once per pool (N=10).
- `judges.py` — 4 LLM judges: faithfulness, context_relevance, completeness, refusal (boolean, forced tool).
- `eval.py` — 5 configurations, shared calls between them, `report` flag for the detailed report.
- `models.py` — frozen Pydantic v2 result models (ContentEvaluation | RefusalEvaluation, discriminated by `kind`).
- `logging_setup.py` — centralized logging; `configure_logging()` is called only from `eval.py main()`.
- `manage.py` — `status` / `down` (confirmation by typing REMOVE); the only exception is the OpenSearch control-plane client.

## Decisions
- Bedrock boundary: no other module creates `boto3.client("bedrock-runtime")`.
- Structured output only via forced tool call; temperature 0.0 for judges.
- Selection: static top-3; dynamic — score ≥ 0.6 with no fallback to top-1, otherwise the sentinel "not found".
- Baseline TOP_K=4; tagging per article; recency off.
- Refusal is scored by an LLM judge over the whole answer (question + answer), not by keywords.
  `expect_refusal` is the dataset's expectation, `refusal_ok` is the observed behavior.
- Logs never contain prompts, answers, chunk text, key_facts, or secrets.
- Do not delete / recreate / reindex the `novaops-kb` index without an explicit request.
- `.env` is not committed; the PAT from the original README is never reproduced anywhere.

## Done
- All modules above are implemented; eval.py runs against the live collection (exit 0).
- Refusal judge: UNANSWERABLE_AWS → refusal_ok=True in all 5 configs.
- Tests: 224 (unittest, everything mocked, no network; test logs are not written to `logs/`).
- Last commit: `b1a9343 refactor: replace refusal heuristic with LLM judge`.

## Known issues
- 3 failing tests in `tests/test_logging_setup.py` (they expect console=INFO, file=DEBUG),
  while the defaults in `logging_setup.py` were changed to WARNING/WARNING. Need to decide:
  restore the defaults or update the tests. With WARNING, INFO lifecycle lines are not visible in the console.
- ACCESS_REVIEW (expect_refusal=true) → refusal_ok=False in all configs: the model answers
  from the handbook content. To check: the dataset, or the audience filter / content.
- Judge unit tests mock the model — they verify the wiring, not semantic accuracy.
- The refusal judge costs +1 Bedrock call per refusal question × config (~10 calls per run).
- `data/eval_questions_short.jsonl` is staged (not committed); a `QUESTIONS_FILE` line pointing to it
  is commented out in `eval.py` — decide whether to keep it.
- Docs (`docs/architecture-discovery.md`, `docs/code-reuse-analysis.md`) may still
  describe the old `refused()` heuristic — check.