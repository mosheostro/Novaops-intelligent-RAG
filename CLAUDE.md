# CLAUDE.md — conventions for this project

- `client.py` (OpenSearch + Bedrock wiring), `judges.py` (the three eval judges), `subjects.py` / `subjects.json` (subject vocabulary, tagger, cached tags) and `config.py` (configuration) are stable project modules — import from them, don't rewrite them.
The remaining modules are built on top of them: `create_index.py`, `ingest.py`, `retrieval.py`, `planner.py`, `reranker.py` and `eval.py`. The design is in `docs/architecture-discovery.md`.
- **Bedrock boundary:** `client.py` is the sole owner of Bedrock runtime client construction (`boto3.client("bedrock-runtime", ...)`). Application/domain modules — `retrieval.py`, `planner.py`, `subjects.py`, `reranker.py`, `eval.py`, `judges.py`, and any new module — consume the shared `bedrock` object (and `embed_text()`) from `client.py`; they never construct their own Bedrock client, even for "just this one call." This is an architectural rule, not a snapshot of today's code: it keeps Bedrock wiring in one place, keeps domain logic testable by mocking a single shared object, and keeps a future provider swap a one-file change.
`manage.py` is a deliberate exception, but only for the OpenSearch Serverless **control-plane** client (`batch_get_collection`, `delete_collection` — collection lifecycle, not Bedrock and not the data-plane client `client.py` exposes via `opensearch_client()`). That exception does not extend to Bedrock.
- **Configuration:** `config.py` loads `.env` via `load_dotenv(find_dotenv())` and requires every var below. Import `config` first in every entry point. If any var is missing, 
STOP and ask me to add it — never guess, default, or hard-code a value. Region and model IDs come from `config`, never from literals.
Vars: `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` (Bedrock access), `AWS_REGION` (the collection's region, e.g. `us-east-1`), 
`BEDROCK_MODEL_ID` (e.g. `us.amazon.nova-2-lite-v1:0`), 
`BEDROCK_EMBEDDING_MODEL_ID` (e.g. `amazon.titan-embed-text-v2:0`), 
and `OPENSEARCH_COLLECTION` (the live collection's name — the endpoint resolves from it). `.env.example` is the template; never commit `.env`.
- The OpenSearch collection is already provisioned and the `novaops-kb` index may already be populated. Never drop, delete, recreate or re-ingest it unless I explicitly ask; 
`create_index.py` and `ingest.py` verify by default and only write to an empty index.
- Call models with boto3 Bedrock Converse; keep each model call in one small function so a provider swap is easy. 
For structured output (subject tags, rerank scores), a forced tool call beats parsing prose.
- Comment only the non-obvious AI/SDK bits — skip the obvious.
