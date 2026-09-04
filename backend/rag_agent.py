"""
PantryBuddy RAG orchestration for POST /v3/chat and /v3/suggest-meals.

Retrieve catalog chunks, then generate a grounded answer with citations
or return ranked recipe suggestions for meal planning.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from generators import generate_chat_answer
from retrievers import RetrievedChunk, get_retriever
from v3_api_contract import (
    CONTRACT_VERSION,
    DEFAULT_SUGGESTION_COUNT,
    DEFAULT_TOP_K,
    LOW_RECALL_ANSWER,
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


def _suggestion_count(body: Mapping[str, Any]) -> int:
    if "count" in body:
        return int(body["count"])
    return DEFAULT_SUGGESTION_COUNT


def _recipe_index(recipes: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for recipe in recipes:
        if not isinstance(recipe, Mapping):
            continue
        recipe_id = recipe.get("id")
        if recipe_id:
            index[str(recipe_id)] = recipe
    return index


def _empty_nutrition() -> dict[str, Any]:
    return {
        "calories": None,
        "proteinGrams": None,
        "carbsGrams": None,
        "fatGrams": None,
    }


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


def chunk_to_suggestion(
    chunk: RetrievedChunk,
    catalog: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Map a retrieved chunk to a RecipeSummary, hydrating from catalog when possible."""
    catalog = catalog or {}
    source = catalog.get(chunk.recipe_id or "") if chunk.recipe_id else None

    if isinstance(source, Mapping):
        return {
            "id": source.get("id") or chunk.recipe_id,
            "title": source.get("title") or chunk.title,
            "mealType": source.get("mealType") or chunk.meal_type,
            "diet": source.get("diet") or chunk.diet,
            "cuisine": source.get("cuisine") or chunk.cuisine,
            "sourceName": source.get("sourceName") or chunk.source_name,
            "sourceUrl": source.get("sourceUrl") or chunk.source_url,
            "ingredients": source.get("ingredients") or [],
            "instructions": source.get("instructions") or [],
            "nutrition": source.get("nutrition") or _empty_nutrition(),
        }

    return {
        "id": chunk.recipe_id,
        "title": chunk.title or chunk.recipe_id or "Recipe",
        "mealType": chunk.meal_type,
        "diet": chunk.diet,
        "cuisine": chunk.cuisine,
        "sourceName": chunk.source_name,
        "sourceUrl": chunk.source_url,
        "ingredients": [],
        "instructions": [],
        "nutrition": _empty_nutrition(),
    }


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
    *,
    retriever: Any | None = None,
) -> dict[str, Any]:
    query = str(body.get("query") or "").strip()
    filters = _normalize_filters(body.get("filters"))
    count = _suggestion_count(body)
    top_k = max(_top_k(body), count)

    active_retriever = retriever or get_retriever(recipes)
    chunks = active_retriever.retrieve(query, filters=filters, top_k=top_k)

    if not chunks:
        return {
            "suggestions": [],
            "citations": [],
            "apiContractVersion": CONTRACT_VERSION,
        }

    catalog = _recipe_index(recipes)
    suggestions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for chunk in chunks:
        suggestion = chunk_to_suggestion(chunk, catalog)
        recipe_id = str(suggestion.get("id") or "")
        if recipe_id and recipe_id in seen_ids:
            continue
        if recipe_id:
            seen_ids.add(recipe_id)
        suggestions.append(suggestion)
        if len(suggestions) >= count:
            break

    return {
        "suggestions": suggestions,
        "citations": build_citations(chunks[: len(suggestions)]),
        "apiContractVersion": CONTRACT_VERSION,
    }
