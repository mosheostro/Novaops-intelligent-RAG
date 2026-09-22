# NovaOps Intelligent RAG

A filtered and reranked retrieval-augmented generation (RAG) pipeline over the NovaOps knowledge base, built on Amazon Bedrock and Amazon OpenSearch Serverless. It combines semantic vector retrieval, a hard audience/access boundary, soft subject-based metadata filtering, listwise reranking with a language model, adaptive context selection and grounded answer generation. An evaluation harness measures each mechanism on its own and in combination, so the effect of every stage is visible rather than assumed.

> **Status: design and configuration baseline.** Configuration, the subject vocabulary and tagger, the OpenSearch/Bedrock wiring and the evaluation judges exist. The retrieval pipeline and the evaluation harness are the next implementation phase. See [Project structure](#project-structure) for what is implemented and what is planned.

## Architecture

```
Question + caller role (+ optional "updated after" date)
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
| Context selection | **Static** keeps the top 3. **Dynamic** keeps every candidate scoring ≥ 0.6 and, if none qualifies, returns an explicit "not found" instead of falling back to the best guess. | Low-confidence retrieval is never presented as valid evidence. |
| LLM | **Answer synthesis** from the selected evidence only; it refuses when the context does not contain the answer. | — |

An optional recency filter (chunks updated on or after a caller-supplied date) is available and is off unless a date is given.

## Access control

Access control is hard security filtering, not a relevance signal, and it is enforced separately from the subject and recency filters described above.

- The currently supported audiences are `employee` and `manager`.
- An `employee` query is restricted to chunks with `audience: all`.
- A `manager` query has no audience restriction within the corpus.
- Any other value — an unrecognized role, a typo, an empty string — **fails closed**: the request is rejected before an OpenSearch query is issued, rather than being treated as unrestricted or silently narrowed to "no results".
- The audience filter is applied **inside** the k-NN query itself, never as a post-filter, so an unauthorized chunk is never ranked or returned even transiently.

## Evaluation

The evaluation harness runs the shared question set (`data/eval_questions.jsonl`, 10 questions, including an access-control case and an unanswerable case) through five configurations and scores them with the project's judges (faithfulness, context relevance, completeness, plus a refusal check). The access filter is on in **every** configuration; security is never the variable being measured.

| # | Configuration | Retrieval | Filter | Rerank | Final context |
|---|---|---|---|---|---|
| 1 | baseline | vector, k = 4 | access only | no | 4 chunks |
| 2 | filter-only | vector, k = 4 | access + subject | no | 4 chunks |
| 3 | rerank-only | vector, N = 10 | access only | yes | static top 3 |
| 4 | filter + rerank, static | vector, N = 10 | access + subject | yes | static top 3 |
| 5 | filter + rerank, dynamic | vector, N = 10 | access + subject | yes | every score ≥ 0.6 |

Results are not published yet; they will be added once the harness has run.

## Project structure

```
config.py            Central configuration: loads .env, validates it, exposes settings   [implemented]
client.py            OpenSearch Serverless + Bedrock wiring, embeddings, shared constants [implemented]
judges.py            Faithfulness, context relevance, completeness, refusal check         [implemented]
subjects.py          Subject vocabulary, Nova tagger, cached tagging                      [implemented]
subjects.json        Cached subject tags for each document                                [implemented]
create_index.py      Index mapping; verifies an existing index rather than replacing it   [planned]
ingest.py            Frontmatter parsing, chunking, tagging, embedding, indexing          [planned]
retrieval.py         Access/subject/recency filters, k-NN search, answer generation       [planned]
planner.py           Question → subjects (fail-open subject planner)                      [planned]
reranker.py          Listwise reranker and the static/dynamic context cuts               [planned]
eval.py              The five-configuration evaluation harness                            [planned]
tests/               Unit tests (configuration today)                                     [in progress]
data/                The NovaOps corpus and the evaluation questions
docs/                Architecture and design decisions
requirements.txt     Python dependencies
.env.example         Configuration template (placeholders only)
setup.sh, setup.ps1  Bootstrap scripts (virtual environment, dependencies, .env check)
CLAUDE.md            Working conventions for AI-assisted development
```

## Data

`data/` contains the NovaOps corpus the project runs on, and it is intentionally part of this repository. It holds 32 Markdown documents: 15 in `handbook/` (company-wide, `audience: all`) and 17 in `manager_playbook/` (manager-only, `audience: manager`). Each document starts with frontmatter (`last_updated`, `corpus`, `audience`), which is the authoritative source for the access and recency metadata and is stripped before embedding. Documents are split into 250-word chunks with 50 words of overlap, which yields 400 chunks. `data/eval_questions.jsonl` holds the evaluation questions with their required facts and expected refusals.

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

## Security

- Never commit credentials. `.env` is ignored by Git, and `.env.example` contains placeholders only.
- Configuration comes from the environment and is validated by `config.py` before use; no credential is stored in the source.
- If a credential is ever exposed, rotate it immediately.

## Cost awareness

Amazon Bedrock model invocations and Amazon OpenSearch Serverless capacity may incur AWS charges. Review current AWS pricing before running ingestion or the evaluation, which makes many model calls.

## License and provenance

Licensing and provenance for this repository are not yet finalized, and no license has been chosen. Some bundled material (the `data/` corpus, `client.py`, `judges.py`) was provided to the author as starting material.
