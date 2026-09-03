"""
PantryBuddy RAG orchestration for POST /v3/chat.

Retrieve catalog chunks, then generate a grounded answer with citations.
Suggest-meals remains intentionally unimplemented in this module.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from generators import generate_chat_answer
from retrievers import RetrievedChunk, get_retriever
from v3_api_contract import (
    CONTRACT_VERSION,
    DEFAULT_TOP_K,
    LOW_RECALL_ANSWER,
    not_implemented_payload,
)


def _last_user_message(messages: Sequence[Mapping[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content") or "").strip()
    raise ValueError("'messages' must include at least one user message.")


def _normalize_filters(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    filters: dict[str, str] = {}
    for key, value in raw.items():
        if value is None:
            continue
        text = str(value).strip()
        if text:
            filters[key] = text
    return filters or None


def _top_k(body: Mapping[str, Any]) -> int:
    retrieval = body.get("retrieval") or {}
    if isinstance(retrieval, Mapping) and "topK" in retrieval:
        return int(retrieval["topK"])
    return DEFAULT_TOP_K


def build_citations(chunks: Sequence[RetrievedChunk]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None]] = set()

    for chunk in chunks:
        key = (chunk.recipe_id, chunk.source_url)
        if key in seen:
            continue
        seen.add(key)

        excerpt = " ".join(chunk.text.split())
        if len(excerpt) > 220:
            excerpt = excerpt[:217] + "..."

        citation: dict[str, Any] = {
            "sourceUrl": chunk.source_url or "",
            "sourceName": chunk.source_name or "",
            "excerpt": excerpt,
        }
        if chunk.recipe_id:
            citation["recipeId"] = chunk.recipe_id
        if chunk.title:
            citation["title"] = chunk.title
        citations.append(citation)

    return citations


def run_chat(
    body: Mapping[str, Any],
    recipes: Sequence[Mapping[str, Any]],
    *,
    retriever: Any | None = None,
    generator_client: Any | None = None,
) -> dict[str, Any]:
    messages = body.get("messages") or []
    query = _last_user_message(messages)
    filters = _normalize_filters(body.get("filters"))
    top_k = _top_k(body)

    active_retriever = retriever or get_retriever(recipes)
    chunks = active_retriever.retrieve(query, filters=filters, top_k=top_k)

    if not chunks:
        return {
            "answer": LOW_RECALL_ANSWER,
            "citations": [],
            "apiContractVersion": CONTRACT_VERSION,
        }

    answer = generate_chat_answer(messages, chunks, client=generator_client)
    return {
        "answer": answer,
        "citations": build_citations(chunks),
        "apiContractVersion": CONTRACT_VERSION,
    }


def run_suggest_meals(
    body: Mapping[str, Any],
    recipes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    del body, recipes
    return not_implemented_payload("suggest_meals")
