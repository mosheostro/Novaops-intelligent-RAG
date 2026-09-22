# Security Concepts — Access Control

This document is the detailed reference for the project's one hard security boundary: audience-based access control. `README.md` states the same rules briefly for a public audience; `docs/architecture-discovery.md` §5 places it in the wider filter architecture. This document explains the reasoning.

## Audience model

Every retrieval call is made on behalf of a caller with a **role**, passed as `audience`. The currently supported audiences are:

- `employee`
- `manager`

This list — `SUPPORTED_AUDIENCES` in `retrieval.py` — is the single authoritative definition. Nothing else in the codebase maintains a second copy of it, and `build_filter`, `knn_search` and `count_candidates` all validate through `access_filter`, so there is exactly one place a role is judged supported or not.

| Audience | Policy |
|---|---|
| `employee` | Restricted to chunks where `audience: all`. |
| `manager` | No audience restriction — sees everything **in the existing corpus**. This is not a claim about any future or hypothetical content; it is bounded by what the corpus actually contains today. |

## Fail-closed access control

The rule is:

```text
known role   -> that role's specific access policy
unknown role -> reject the request
```

An audience outside `SUPPORTED_AUDIENCES` — a typo, an empty string, a role that doesn't exist yet, a role from a different system — is never given a policy. It is rejected.

This is a deliberate choice against the more common shortcut of `if employee: restrict, else: unrestricted`. That shortcut is a security bug wearing the shape of a two-branch conditional: it treats "anything I didn't specifically restrict" as "safe to leave unrestricted", which is backwards. The default for anything not explicitly recognized must be **deny**, not **allow**.

## Why unknown != manager

An unsupported audience must never inherit the permissions of the broadest supported audience.

Concretely: if a caller passes `"marketing"`, `"HR"`, an empty string, or a role that only exists in some other system's vocabulary, that request must not silently receive manager-level access. `manager` is not a fallback or a default — it is one specific, deliberately granted policy for one specific, named role. Nothing about the *absence* of a match should be read as evidence that the broadest policy applies. The correct reading of "I don't recognize this role" is "I have no policy for this", which means the request cannot proceed at all.

This also protects against a class of mistakes that composition alone doesn't catch: a caller that passes the wrong variable, a role string with different casing (`"Employee"`), or a role imported from a future extension that hasn't been given a policy here yet. Each of those must fail loudly rather than fail into the most permissive branch.

## Enforcement point

Validation happens in `retrieval.py`, in `access_filter`, and it happens **before** any OpenSearch access:

- `build_filter` calls `access_filter` first (before `subject_terms` or `recency_range`), so an unsupported audience is rejected before the soft filters are even considered.
- `knn_search` calls `build_filter` before it embeds the query text or calls the OpenSearch client — an unsupported audience raises before an embedding call is made and before any network request is sent.
- `count_candidates` calls `build_filter` before calling `client.count` — the same guarantee for the diagnostic/eval path.
- For a supported `employee` audience, the resulting `{"term": {"audience": "all"}}` clause is placed **inside** the k-NN query's `filter`, never applied as a `post_filter` after ranking. A `post_filter` would let the search engine rank against the whole corpus first and only discard disallowed hits afterward — meaning a manager-only chunk would briefly participate in the ranking computation for an employee's query. Filtering inside the k-NN block means the engine never visits a disallowed chunk in the first place.

## Defense in depth

The tests in `tests/test_retrieval.py` verify this invariant deterministically and offline: that `employee` and `manager` each get their documented policy, that every other value raises, and that neither `knn_search` nor `count_candidates` reaches the fake OpenSearch client when the audience is rejected. These tests are a safety net that catches a regression — they are not themselves the enforcement. The actual enforcement is the validation inside `access_filter` in the retrieval layer; the tests exist to keep that one piece of logic honest as the code around it changes.

## Extensibility

Adding a new supported role later means two changes together, not one:

1. Add the role's name to `SUPPORTED_AUDIENCES`.
2. Give it an explicit branch in `access_filter` that states its policy.

Widening `SUPPORTED_AUDIENCES` alone, without also defining what that role is allowed to see, is not a complete or safe change — a role with no defined policy has no business being marked as supported. This document does not define policies for hypothetical future roles (a "marketing" or "HR" audience, a bot account, etc.); none exist in the system today, and inventing their access rules ahead of an actual requirement would be a guess, not a security decision.
