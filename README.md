# NovaOps Intelligent RAG

A filtered and reranked retrieval-augmented generation (RAG) pipeline over the NovaOps knowledge base, built on Amazon Bedrock and Amazon OpenSearch Serverless. It combines semantic vector retrieval, a hard audience/access boundary, soft subject-based metadata filtering, listwise reranking with a language model, adaptive context selection and grounded answer generation. An evaluation harness measures each mechanism on its own and in combination, so the effect of every stage is visible rather than assumed.

> **Status: implemented.** The retrieval pipeline, the five-configuration evaluation harness (with saved run artifacts) and a Streamlit dashboard (chat + evaluation laboratory) run against the live collection. An MCP server (STDIO and Streamable HTTP; three tools and one resource), a command-line MCP client and an MCP page in the dashboard expose the same question-answering use case over the Model Context Protocol — see [MCP server](#mcp-server). A loopback-only REST API offers it to any HTTP client — see [REST API](#rest-api). The current architecture is documented in [`docs/architecture.md`](docs/architecture.md).

## Architecture

```
Question + caller role (+ optional cutoff date: last_updated >= cutoff)
  → audience / access policy      hard filter derived from the caller's role
  → subject planning              forced tool call over a fixed vocabulary; [] means "no subject filter"
  → OpenSearch k-NN retrieval     all filters applied inside the vector query
  → candidate pool                N = 10 candidates (k = 4 in the plain configurations)
  → listwise reranker             one Amazon Nova call scores every candidate
  → static / dynamic selection    top 3, or every candidate scoring ≥ 0.6
  → grounded answer               answers only from the selected evidence
```

Each stage has one job:

| Stage | Role | Failure behavior |
|---|---|---|
| Access filter | **Hard security boundary.** Employees can only retrieve `audience: all` content; managers see everything in the corpus. Applied inside the k-NN query on every path. | Fails **closed**: it either restricts, is absent, or the request is rejected outright for an unsupported role — see [Access control](#access-control). |
| Subject filter | **Soft relevance mechanism.** A planner maps the question onto a shared subject vocabulary; only chunks carrying one of those subjects are searched. | Fails **open**: an empty plan means no subject restriction. |
| Vector search | **Recall.** Finds semantically close chunks. | — |
| Reranker | **Precision and order.** Scores all candidates together against the question. | Candidates the model omits score 0. |
| Context selection | **Static** keeps the top 3. **Dynamic** keeps every candidate scoring ≥ 0.6 and, if none qualifies, selects zero chunks (`status = "not_found"`) instead of falling back to the best guess; the model is then prompted with "not found". | Low-confidence retrieval is never presented as valid evidence. |
| LLM | **Answer synthesis** from the selected evidence only; it refuses when the context does not contain the answer. | — |

An optional recency cutoff — one date, keeping chunks with `last_updated >= cutoff` (inclusive) — is off unless a date is given. It is independent of the configuration choice, is exposed in the dashboard chat, and is not used by evaluation runs.

## Access control

Access control is hard security filtering, not a relevance signal, and it is enforced separately from the subject and recency filters described above.

- The currently supported audiences are `employee` and `manager`.
- An `employee` query is restricted to chunks with `audience: all`.
- A `manager` query has no audience restriction within the corpus.
- Any other value — an unrecognized role, a typo, an empty string — **fails closed**: the request is rejected before an OpenSearch query is issued, rather than being treated as unrestricted or silently narrowed to "no results".
- The audience filter is applied **inside** the k-NN query itself, never as a post-filter, so an unauthorized chunk is never ranked or returned even transiently.

## Evaluation

The evaluation harness runs a question set (by default `data/eval_questions.jsonl`, 10 questions, including an access-control case and an unanswerable case; `--questions PATH` selects another) through five configurations and scores them with the project's LLM judges (faithfulness, context relevance, completeness, plus an LLM refusal judge for questions expected to be refused). The access filter is on in **every** configuration; security is never the variable being measured. The planner runs once per question and reranking once per unique candidate pool, shared by the static and dynamic cuts.

```bash
python eval.py                                   # print the report
python eval.py --save                            # also save runs/<timestamp>_<set>.json
python eval.py --ids SEV_3YR,ACCESS_REVIEW --config baseline --config "filter + rerank dynamic" \
               --cutoff 2025-04-28 --save  # one experiment: questions x configurations x cutoff
```

| # | Configuration | Retrieval | Filter | Rerank | Final context |
|---|---|---|---|---|---|
| 1 | baseline | vector, k = 4 | access only | no | 4 chunks |
| 2 | filter-only | vector, k = 4 | access + subject | no | 4 chunks |
| 3 | rerank-only | vector, N = 10 | access only | yes | static top 3 |
| 4 | filter + rerank, static | vector, N = 10 | access + subject | yes | static top 3 |
| 5 | filter + rerank, dynamic | vector, N = 10 | access + subject | yes | every score ≥ 0.6 |

Results are not published in this README; saved runs can be browsed in the dashboard.

## Dashboard

```bash
streamlit run ui/app.py        # from the project root; needs APP_PASSWORD (see below)
```

The dashboard is behind a password: set `APP_PASSWORD` in your local `.env` (or in Streamlit secrets when deployed). If it is missing or blank, the dashboard refuses to start with a configuration error — there is no passwordless mode. `eval.py`, the tests and the RAG modules never need it.

- **Chat**: ask a custom question as a demo role (employee/manager — not authentication), pick one of the five configurations and an optional cutoff date, optionally score with judges, and inspect the sources and the full pipeline trace.
- **Evaluation runs**: configure an experiment — pick test cases from `data/eval_questions.jsonl` by id, one or more of the five configurations, and an optional cutoff — review the run summary and estimated model calls, confirm the cost, and launch it as a separate `eval.py` subprocess; browse saved runs. Each test case runs as its own dataset audience; there is no audience override and no access-filter control.
- **Run detail**: the per-configuration summary, a questions × configurations matrix, and a per-question drill-down.
- **MCP server**: an MCP client of a separately running MCP server (see [MCP server](#mcp-server)) — discovery, health check and questions over the protocol. It never starts or stops the server.
- **API & MCP Help**: a manual for the REST API and the MCP server — how to start them and try them with curl, `mcp_client.py` or MCP Inspector. Documentation only: it connects to nothing.

## Project structure

```
config.py            Central configuration: loads .env, validates it, exposes settings
client.py            OpenSearch Serverless + Bedrock wiring, embeddings, shared constants
judges.py            LLM judges: faithfulness, context relevance, completeness, refusal
subjects.py          Subject vocabulary, Nova tagger, cached tagging
subjects.json        Cached subject tags for each document
create_index.py      Index mapping; verifies an existing index rather than replacing it
ingest.py            Frontmatter parsing, chunking, tagging, embedding, indexing (empty index only)
retrieval.py         Access/subject/recency filters, k-NN search, answer generation
planner.py           Question → subjects (fail-open subject planner)
reranker.py          Listwise reranker (ranks only; the cuts live in eval.py)
models.py            Frozen Pydantic domain models — the contract every consumer reads
eval.py              Evaluation harness; CLI --ids/--config/--cutoff/--save/--run-id (--questions for another file)
ask.py               One custom question through one configuration (used by the dashboard)
runs.py              Saved run artifacts under runs/ and the eval.py subprocess launcher
logging_setup.py     Centralized logging configuration (called only from eval.py main())
manage.py            Collection status / teardown (control plane; typed confirmation); collection_health()
mcp_server.py        MCP server (STDIO or Streamable HTTP): ask_rag, health_check, get_rag_capabilities, rag://subjects
mcp_client.py        MCP client: CLI (discover / health / ask) and the synchronous functions the dashboard page uses
api_server.py        REST API (FastAPI, loopback only): /v1/ask, /v1/health, /v1/info, /v1/capabilities, /v1/subjects, /healthz
public_views.py      The public, security-safe views of results that MCP and the REST API return
failures.py          Transport-independent failure categories used by the MCP server and the REST API
ui/                  Streamlit dashboard (app.py, app_pages/, components/, access.py); app_pages/mcp_page.py is the MCP client page
.streamlit/          Dashboard theme
tests/               Unit tests (AWS mocked); real-process tests on loopback; opt-in live REST tests
data/                The NovaOps corpus and the evaluation questions
docs/                Architecture and design decisions
requirements.txt     Python dependencies
requirements-mcp.txt Optional MCP dependency (the SDK); kept out of the dashboard deployment
requirements-api.txt Optional REST API dependencies (FastAPI, uvicorn); kept out of the dashboard deployment
.env.example         Configuration template (placeholders only)
setup.sh, setup.ps1  Bootstrap scripts (virtual environment, dependencies, .env check)
CLAUDE.md            Working conventions for AI-assisted development
```

## Data

`data/` contains the NovaOps corpus the project runs on, and it is intentionally part of this repository. It holds 32 Markdown documents: 15 in `handbook/` (company-wide, `audience: all`) and 17 in `manager_playbook/` (manager-only, `audience: manager`). Each document starts with frontmatter (`last_updated`, `corpus`, `audience`), which is the authoritative source for the access and recency metadata and is stripped before embedding. Documents are split into 250-word chunks with 50 words of overlap, which yields 400 chunks. `data/eval_questions.jsonl` holds the evaluation questions with their required facts and expected refusals. It is the single source of preset evaluation questions; its size is whatever the file contains. Each record is one test case — `id`, `question`, `audience` (the role it runs as), `expect_refusal`, `key_facts`, `report` (CLI detail) and `scenario` (`standard` / `cross_source` / `access_boundary` / `out_of_corpus`, display only).

## AWS prerequisites

- An AWS account.
- Access to the Amazon Bedrock models you configure: a chat model that supports the Converse API with forced tool use (the project is designed around Amazon Nova) and a text-embedding model that returns 1024-dimensional vectors (Amazon Titan Text Embeddings V2 produces these; `client.py` fixes the dimension).
- An Amazon OpenSearch Serverless vector-search collection in the same region, with the network and data-access policies that let your IAM identity create and query an index in it.
- IAM permissions to invoke the Bedrock models, to look up the collection by name in the OpenSearch Serverless control plane, and to use the collection's data plane.
- A region of your choice, set through `AWS_REGION`. It is required configuration, and `config.py` refuses to start without it.

## Configuration

Copy `.env.example` to `.env` and fill in the values. `config.py` loads it with `python-dotenv` and validates it at startup: if any required variable is missing or blank, it stops with one error naming every missing variable. There are no defaults for the region or the model IDs.

| Variable | Purpose |
|---|---|
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Credentials used for Bedrock (and OpenSearch, unless the optional pair below is set) |
| `AWS_REGION` | Region of the Bedrock models and the OpenSearch collection |
| `BEDROCK_MODEL_ID` | Chat model used for tagging, planning, reranking, answering and judging |
| `BEDROCK_EMBEDDING_MODEL_ID` | Embedding model (must return 1024-dimensional vectors) |
| `OPENSEARCH_COLLECTION` | Name of the OpenSearch Serverless collection; its endpoint is resolved from the name |

Optional:

| Variable | Purpose |
|---|---|
| `OPENSEARCH_AWS_ACCESS_KEY_ID`, `OPENSEARCH_AWS_SECRET_ACCESS_KEY` | Separate credentials for OpenSearch Serverless when it lives in a different AWS account than Bedrock. Set both or neither. |
| `OPENSEARCH_ENDPOINT` | Pin a specific collection endpoint and skip the name lookup |

`.env` is local-only and ignored by Git.

## Setup

Requires Python 3.10 or newer.

```bash
git clone https://github.com/mosheostro/Novaops-intelligent-RAG.git
cd Novaops-intelligent-RAG
cp .env.example .env          # then edit .env and fill in your values
bash setup.sh                 # macOS, Linux, Git Bash
```

On Windows PowerShell, run `.\setup.ps1` instead of the last command. The script creates a `.venv` virtual environment, installs `requirements.txt`, and checks that `.env` exists and is complete. It makes no AWS calls.

Activate the environment and run the tests (they need no AWS access):

```bash
source .venv/bin/activate     # Git Bash: source .venv/Scripts/activate   PowerShell: .venv\Scripts\Activate.ps1
python -m unittest
```

The MCP tests need the optional dependency (`pip install -r requirements-mcp.txt`); without it they are skipped with that instruction, and the MCP dependency-boundary tests still run. The REST API tests likewise need `requirements-api.txt`. Some MCP and REST tests start real server processes on loopback ports with placeholder settings; they make no AWS call.

The live REST tests are the only tests that call AWS. They start real REST servers on your `.env` and ask a few questions, so they cost a handful of model calls. They are skipped unless you opt in:

```powershell
$env:NOVAOPS_LIVE_TESTS = "1"; .venv\Scripts\python.exe -m unittest tests.test_api_http -v
```

## MCP server

`mcp_server.py` exposes the knowledge base to MCP clients (MCP Inspector, Claude Code, other agent environments). It is a thin adapter: it calls the same `ask.ask()` use case as the dashboard and the read-only `manage.collection_health()`; retrieval, access control, reranking and judging stay in the core, which never imports the MCP SDK. The server identifies itself as `novaops-knowledge-base`, version `0.2.0`. Stage 1 added the server over STDIO; Stage 2 added Streamable HTTP, the command-based client and the dashboard's MCP page.

```bash
pip install -r requirements-mcp.txt      # optional dependency: the MCP SDK (mcp>=2.3,<3)
```

**Transports.** One server, two transports; the tools, resource and responses are identical on both. Run everything from the project root.

- **STDIO** (default): `python mcp_server.py --role employee`. An MCP client normally starts this process itself; stdout carries only JSON-RPC, and logs go to stderr.
- **Streamable HTTP**: `python mcp_server.py --transport streamable-http --role employee [--port 8000]` serves `http://127.0.0.1:8000/mcp` — one fixed `/mcp` endpoint, stateless, plain JSON responses. It is **loopback-only**: `--host` accepts only `127.0.0.1` (default), `localhost` or `::1`, and anything else is refused at startup, because the HTTP transport has no authentication. On those hosts the SDK's DNS-rebinding protection rejects a foreign `Host` or `Origin` header.

Stop a manually started server with Ctrl+C.

**Client.** `mcp_client.py` runs one MCP interaction per command, against a running HTTP server (`--url`) or a STDIO server it starts for that command (`--role`):

```bash
python mcp_client.py discover --url http://127.0.0.1:8000/mcp        # server name and version, transport, tools and
                                                                     # resources with their descriptions, capabilities,
                                                                     # subjects — no AWS call
python mcp_client.py health --url http://127.0.0.1:8000/mcp          # health_check
python mcp_client.py ask "How does PTO accrue?" --url http://127.0.0.1:8000/mcp \
       [--config "filter + rerank dynamic"] [--judge] [--updated-on-or-after 2025-01-31]
python mcp_client.py discover --role manager                         # the same over STDIO
```

Output is readable text; `--json` prints exactly what the server returned. Errors are one line: an invalid URL or invocation is a usage error (exit 2) that says how to fix it; an unreachable server, a wrong endpoint path, a timeout, a dropped connection or a non-MCP endpoint is reported as such (exit 1, with the start command when nothing is listening); a tool error prints the server's own safe message. If a STDIO server refuses to start, the client prints the server's reason.

**Local demo: separate processes.** The MCP server and the dashboard are independent processes; the dashboard never starts, stops or supervises the server.

```bash
python mcp_server.py --transport streamable-http --role employee               # terminal 1
python mcp_server.py --transport streamable-http --role manager --port 8010    # terminal 2 (optional)
streamlit run ui/app.py                                                        # terminal 3
```

On the dashboard's **MCP server** page, enter `http://127.0.0.1:8000/mcp` (or `:8010` for the manager server) and press **Connect / Refresh**. The page is an MCP client: it shows the server's identity, role, tools, resources, subjects and capabilities, runs the health check and asks questions through `ask_rag` — never through the dashboard's own RAG calls. It accepts loopback URLs only, calls nothing until you connect, and waits up to 120 seconds for a response.

**Role.** `--role` is required: `employee` or `manager`, validated by the same access filter the pipeline uses. There is no default and no fallback; an unsupported role stops the server before it serves anything. The role is fixed for the life of the process and is not a tool argument — over HTTP, every caller of a server gets that server's role, so run one server per role. It is a **server role, not authentication**: it says nothing about who the MCP client is, and whoever starts the process chooses it. The dashboard's sidebar role does not change it.

| Surface | What it does |
|---|---|
| `ask_rag` | Answers one question as the server's role. Arguments: `question` (required, 1–2000 characters), `config` (one of the five configurations, default `filter + rerank dynamic`), `judge` (default `false`), `updated_on_or_after` (optional ISO date `YYYY-MM-DD`). |
| `health_check` | Whether the knowledge base is ready: `ready`, `collection_state`, `index_present`, `chunk_count`, `data_plane_reachable`. An unhealthy collection is a normal result, not an error. |
| `get_rag_capabilities` | The configured role, the five configurations and what each does, the default, judging, security behaviour, input options and the subject vocabulary. |
| `rag://subjects` | The subject vocabulary (`application/json`). |

That is the whole surface: no `get_subjects` tool, no prompts, no resource templates. The subject vocabulary appears both in `get_rag_capabilities` (for clients that use tools only) and as the `rag://subjects` resource; both come from the same constant.

**What a response contains.** `ask_rag` returns a deliberate projection of the domain result: the answer, configuration, role, status (`selected` / `not_found`), planned subjects, cutoff, the number of candidates considered, the selected sources as metadata only (`rank` — 1-based —, `source`, `corpus`, `subjects`, `last_updated`, `rerank_score`), a `security_audit` and, when requested, the judgement. It never contains chunk text, vector scores or the question.

**Security and privacy.** The access filter is applied from the server's role on every request. If the security audit finds content outside the role's permitted audience, the answer, sources and judgement are withheld; the response reports only that a violation happened, how many sources it flagged and a fixed explanation — never which documents. Protocol output (including the server name) carries no collection name, endpoint, index name, region or account identifiers, and neither do the health and request logs. Service failures come back as fixed messages (`service_unavailable`, `service_timeout`, `unsupported_role`); unexpected errors as a generic tool error. The server's stderr is operator output: on a security violation the core's audit log names the flagged files there, and an unexpected error is logged with its traceback.

Limitations: no authentication of MCP callers, deliberately (the role is a startup setting), which is why the HTTP transport is loopback-only; no server-side request timeout — a first call after the knowledge base has been idle can take noticeably longer, so give MCP clients a generous request timeout, and use `health_check` to warm it up.

## REST API

`api_server.py` offers the same question answering to any HTTP client, as a separate local process. It is a thin adapter, a sibling of the MCP server: it calls the existing `ask.ask()` and `manage.collection_health()` use cases and returns the same public views of the results as MCP (`public_views.py`). Retrieval, access control, reranking, the security audit and judging stay in the core. The dashboard does not use it; the dashboard calls the application in-process.

```bash
pip install -r requirements-api.txt                       # optional dependencies: FastAPI and uvicorn
python api_server.py --role employee                      # http://127.0.0.1:8001
python api_server.py --role manager --port 8002           # a second server for the other role
```

The interactive OpenAPI page at `http://127.0.0.1:8001/docs` (and `/openapi.json`) is the authoritative contract. Stop a server with Ctrl+C.

| Endpoint | What it does |
|---|---|
| `POST /v1/ask` | Answers one question as the server's role. JSON body: `question` (required, 1–2000 characters), `config` (one of the five configurations, default `filter + rerank dynamic`), `judge` (`true`/`false`, default `false`), `updated_on_or_after` (optional, exactly `YYYY-MM-DD`). Unknown fields are rejected. |
| `GET /v1/health` | **Readiness** — a backend check of the knowledge base: `ready`, `collection_state`, `index_present`, `chunk_count`, `data_plane_reachable`. 200 when ready, 503 with the same body when not. |
| `GET /healthz` | **Liveness** — the process is up. No backend call. |
| `GET /v1/info` | Name, server version, API version and the server's role. |
| `GET /v1/capabilities` | The five configurations and what each does, the default, judging, security behaviour and request limits. |
| `GET /v1/subjects` | The subject vocabulary. |

```bash
curl -s http://127.0.0.1:8001/v1/ask -H "Content-Type: application/json" \
     -d '{"question": "Does the company match my 401k contributions?"}'
```

**Role.** `--role` is required: `employee` or `manager`, validated at startup by the same access filter the pipeline uses. It is fixed for the life of the process and is not part of the request: a body that contains `role` is rejected (422). Run one server per role. It is a server setting, not authentication.

**Responses.** `POST /v1/ask` returns the same projection as MCP's `ask_rag`: the answer, configuration, role, status, planned subjects, cutoff, the number of candidates considered, the sources as metadata only, a `security_audit` and, when requested, the judgement — never chunk text, vector scores or the question. `not_found` is a normal 200 result. So is a failed security audit: the answer, sources and judgement are withheld, and only the count of flagged sources is reported.

**Errors.** Every error is an RFC 9457 `application/problem+json` body (`type`, `title`, `status`, `detail`, plus `errors` for validation) with fixed wording — never the request's values or an exception's message. Invalid input is 422; a body that is not declared `application/json` is 415; an unknown path is 404 and a wrong method 405; an unavailable knowledge base or model service is 503 and a timeout 504; anything unexpected is 500.

**Security.** There is no authentication in this version, so the server binds to loopback only (`--host` accepts `127.0.0.1`, `localhost` or `::1`) and protects itself against browsers: a foreign `Host` header is rejected (400), request bodies must be declared JSON, and there is no CORS — so a web page cannot send a question cross-site. Responses and logs carry no collection name, endpoint, index name, region or account identifiers, and the server never logs questions or answers.

Limitations: no authentication, no rate limiting and no server-side timeout; a client that disconnects does not cancel model calls already under way, and `judge: true` adds 3–4 model calls. A first question after the knowledge base has been idle can take noticeably longer — call `/v1/health` to warm it up.

## Deployment (Streamlit Community Cloud)

- Streamlit Community Cloud has no `.env`: supply the six required variables (and any optional ones) plus `APP_PASSWORD` as the app's **Secrets**, e.g. `AWS_REGION = "<your-region>"` in TOML.
- `ui/app.py` bridges those secrets into the environment before `config.py` validates it, without overwriting values that are already set (precedence: shell environment > local `.env` > Streamlit secrets). `config.py` itself stays independent of Streamlit.
- `APP_PASSWORD` protects the whole dashboard. It is a basic shared-password gate for a demo — not user authentication or authorization. The sidebar Employee/Manager role remains a demo retrieval-audience selector.
- The deployment installs `requirements.txt` only, without the MCP SDK; there the MCP server page explains how to install it locally instead of failing. The rest of the dashboard is unaffected.
- The REST API is not part of the deployment: it is a separate, loopback-only local process.
- Never commit real credentials or passwords: `.env` and `.streamlit/secrets.toml` are git-ignored; `.env.example` holds placeholders only.

## Security

- Never commit credentials. `.env` is ignored by Git, and `.env.example` contains placeholders only.
- Configuration comes from the environment and is validated by `config.py` before use; no credential is stored in the source.
- If a credential is ever exposed, rotate it immediately.

## Cost awareness

Amazon Bedrock model invocations and Amazon OpenSearch Serverless capacity may incur AWS charges. Review current AWS pricing before running ingestion or the evaluation, which makes many model calls.

## License and provenance

Licensing and provenance for this repository are not yet finalized, and no license has been chosen. Some bundled material (the `data/` corpus, `client.py`, `judges.py`) was provided to the author as starting material.
