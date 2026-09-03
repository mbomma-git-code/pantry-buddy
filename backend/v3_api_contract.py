"""
PantryBuddy RAG API v3 — request/response contract, retrieval, and citation rules.

This module is the single source of truth for v3 semantics until OpenAPI is added.
Lambda routes: POST /v3/chat, POST /v3/suggest-meals (see config.API_ENDPOINTS).

Endpoints
---------

**POST /v3/chat** — Conversational Q&A grounded in the knowledge base.
- Use for substitutions, technique questions, narrative explanations, and
  multi-turn context. The model must only assert recipe facts present in
  retrieved chunks or clearly label speculation.

**POST /v3/suggest-meals** — Retrieval-first meal ideas for a natural-language
  query (e.g. “high-protein vegetarian dinners”). Returns ranked suggestions
  with citations; this is not the same as v2’s deterministic weekly planner.

Retrieval rules (server-side)
-----------------------------

1. **Hybrid search**: Combine Bedrock Knowledge Base semantic retrieval with
   metadata filters when the client sends ``filters`` (``mealType``, ``diet``,
   ``cuisine``, ``sourceName``). Omitting filters means semantic-only
   constraints from the user text.

2. **Corpus preference** (field ``retrieval.corpusPreference``):
   - ``structured_first`` (default): query structured recipe documents (corpus A)
     first; include raw page chunks (corpus B) only when the query is
     narrative-heavy or structured retrieval yields insufficient context.
   - ``structured``: structured corpus only.
   - ``raw``: raw narrative corpus only (noisier; use sparingly).

3. **Limits**: ``retrieval.topK`` caps chunks returned before MMR/reranking
   (default and bounds in constants below).

4. **Low recall**: If retrieval returns no relevant chunks, the assistant must
   state that the catalog has no matching grounded content — no inventing
   recipes or sources.

Citation rules
--------------

1. **Attribution**: Any specific recipe claim (title, ingredient amounts, steps)
   must be tied to a citation object including at least ``sourceUrl`` and
   ``sourceName`` from retrieval metadata when available, plus stable
   ``recipeId`` when the chunk maps to corpus A.

2. **No orphan facts**: The LLM system prompt must instruct: use only retrieved
   context for factual recipe statements; general cooking knowledge may be
   labeled as non-catalog if not in chunks.

3. **Corpus B**: Narrative chunks must still cite ``sourceUrl`` / ``sourceName``
   when the KB provides them; excerpts in citations should be short spans from
   retrieved text.

Response shapes
---------------

**chat** (200): ``{ "answer": str, "citations": [Citation, ...] }``
**suggest-meals** (200): ``{ "suggestions": [RecipeSummary, ...], "citations": [...] }``

Local v3 falls back to lexical search over the canonical catalog when
``KNOWLEDGE_BASE_ID`` is unset. In production, Lambda uses Bedrock
``Retrieve`` plus ``InvokeModel`` (Claude) with the same citation rules.

Where ``Citation`` is ``{ "recipeId"?: str, "sourceUrl": str, "sourceName": str,
"excerpt"?: str }`` and ``RecipeSummary`` aligns with structured metadata
(``id``, ``title``, ``mealType``, …) plus citation fields as needed.
"""

from __future__ import annotations

from typing import Any, Mapping

# Bump when breaking request/response or semantic rules change.
CONTRACT_VERSION = "3.0"

NOT_IMPLEMENTED_CODE = "NOT_IMPLEMENTED"

LOW_RECALL_ANSWER = (
    "The catalog has no matching grounded content for that request. "
    "I am not inventing recipes or sources."
)

DEFAULT_TOP_K = 8
MAX_TOP_K = 25
MIN_TOP_K = 1

DEFAULT_SUGGESTION_COUNT = 5
MAX_SUGGESTION_COUNT = 20
MIN_SUGGESTION_COUNT = 1

ALLOWED_MESSAGE_ROLES = frozenset({"user", "assistant"})
ALLOWED_CORPUS_PREFERENCES = frozenset({"structured", "raw", "structured_first"})

FILTER_KEYS = frozenset({"mealType", "diet", "cuisine", "sourceName"})

OPTIONAL_SUGGEST_CONTEXT_FIELDS = frozenset(
    {"preferences", "dietaryRestrictions", "allergies", "excludedIngredients"}
)


def _non_empty_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{field}' must be a non-empty string.")
    return value.strip()


def _optional_filters(payload: Mapping[str, Any]) -> None:
    raw = payload.get("filters")
    if raw is None:
        return
    if not isinstance(raw, dict):
        raise ValueError("'filters' must be an object when provided.")
    unknown = set(raw) - FILTER_KEYS
    if unknown:
        raise ValueError(f"Unknown filter keys: {sorted(unknown)}")
    for key in FILTER_KEYS:
        val = raw.get(key)
        if val is None:
            continue
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"filters.{key} must be a non-empty string when provided.")


def _optional_retrieval(payload: Mapping[str, Any]) -> None:
    raw = payload.get("retrieval")
    if raw is None:
        return
    if not isinstance(raw, dict):
        raise ValueError("'retrieval' must be an object when provided.")
    pref = raw.get("corpusPreference", "structured_first")
    if pref not in ALLOWED_CORPUS_PREFERENCES:
        raise ValueError(
            "'retrieval.corpusPreference' must be one of: "
            + ", ".join(sorted(ALLOWED_CORPUS_PREFERENCES))
        )
    top_k = raw.get("topK", DEFAULT_TOP_K)
    if not isinstance(top_k, int) or isinstance(top_k, bool):
        raise ValueError("'retrieval.topK' must be an integer.")
    if top_k < MIN_TOP_K or top_k > MAX_TOP_K:
        raise ValueError(
            f"'retrieval.topK' must be between {MIN_TOP_K} and {MAX_TOP_K}."
        )


def validate_v3_chat_request(body: Mapping[str, Any]) -> None:
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object.")
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("'messages' must be a non-empty array.")
    for idx, msg in enumerate(messages):
        if not isinstance(msg, dict):
            raise ValueError(f"messages[{idx}] must be an object.")
        role = msg.get("role")
        if role not in ALLOWED_MESSAGE_ROLES:
            raise ValueError(
                f"messages[{idx}].role must be one of {sorted(ALLOWED_MESSAGE_ROLES)}."
            )
        _non_empty_str(msg.get("content"), f"messages[{idx}].content")
    last_user = False
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user = True
            break
    if not last_user:
        raise ValueError("'messages' must include at least one user message.")
    _optional_filters(body)
    _optional_retrieval(body)


def _validate_string_list_field(name: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, str):
        return
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return
    raise ValueError(f"'{name}' must be a string or a list of strings when provided.")


def validate_v3_suggest_meals_request(body: Mapping[str, Any]) -> None:
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object.")
    _non_empty_str(body.get("query"), "query")
    count = body.get("count", DEFAULT_SUGGESTION_COUNT)
    if not isinstance(count, int) or isinstance(count, bool):
        raise ValueError("'count' must be an integer.")
    if count < MIN_SUGGESTION_COUNT or count > MAX_SUGGESTION_COUNT:
        raise ValueError(
            f"'count' must be between {MIN_SUGGESTION_COUNT} and {MAX_SUGGESTION_COUNT}."
        )
    _optional_filters(body)
    _optional_retrieval(body)
    for field in OPTIONAL_SUGGEST_CONTEXT_FIELDS:
        if field not in body:
            continue
        if field == "preferences":
            val = body[field]
            if val is None:
                continue
            if isinstance(val, (str, dict)):
                continue
            if isinstance(val, list) and all(isinstance(item, str) for item in val):
                continue
            raise ValueError(
                "'preferences' must be a string, object, or list of strings when provided."
            )
        else:
            _validate_string_list_field(field, body[field])


def not_implemented_payload(operation: str) -> dict[str, Any]:
    return {
        "error": "RAG v3 retrieval and generation are not enabled in this deployment yet.",
        "code": NOT_IMPLEMENTED_CODE,
        "operation": operation,
        "apiContractVersion": CONTRACT_VERSION,
    }
