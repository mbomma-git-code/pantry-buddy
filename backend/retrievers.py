"""
RAG retrieval backends for PantryBuddy v3 chat.

Local lexical search over the canonical catalog is the default. When
KNOWLEDGE_BASE_ID is set, Bedrock Knowledge Bases Retrieve is used instead.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

try:
    import boto3  # pyright: ignore[reportMissingImports]
except ImportError:
    boto3 = None

from config import AWS_CONFIG
from v3_api_contract import FILTER_KEYS

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "can",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "me",
        "my",
        "of",
        "on",
        "or",
        "the",
        "to",
        "what",
        "with",
        "you",
    }
)


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    score: float
    recipe_id: str | None = None
    title: str | None = None
    source_url: str | None = None
    source_name: str | None = None
    meal_type: str | None = None
    diet: str | None = None
    cuisine: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class Retriever(Protocol):
    def retrieve(
        self,
        query: str,
        *,
        filters: Mapping[str, str] | None = None,
        top_k: int = 8,
    ) -> list[RetrievedChunk]:
        ...


def _tokenize(text: str) -> list[str]:
    return [
        token.lower()
        for token in _TOKEN_RE.findall(text or "")
        if token.lower() not in _STOPWORDS and len(token) > 1
    ]


def _filter_matches(recipe: Mapping[str, Any], filters: Mapping[str, str] | None) -> bool:
    if not filters:
        return True

    for key, expected in filters.items():
        if expected is None:
            continue
        actual = recipe.get(key)
        if actual is None:
            return False
        if str(actual).strip().lower() != str(expected).strip().lower():
            return False
    return True


def _recipe_search_blob(recipe: Mapping[str, Any]) -> str:
    parts: list[str] = [
        str(recipe.get("title") or ""),
        str(recipe.get("mealType") or ""),
        str(recipe.get("diet") or ""),
        str(recipe.get("cuisine") or ""),
        str(recipe.get("sourceName") or ""),
    ]
    for ingredient in recipe.get("ingredients") or []:
        if isinstance(ingredient, Mapping):
            parts.append(str(ingredient.get("item") or ""))
            parts.append(str(ingredient.get("preparation") or ""))
    for instruction in recipe.get("instructions") or []:
        if isinstance(instruction, Mapping):
            parts.append(str(instruction.get("text") or ""))
        else:
            parts.append(str(instruction))
    return " ".join(parts)


def _format_recipe_chunk(recipe: Mapping[str, Any]) -> str:
    lines = [
        f"title: {recipe.get('title') or ''}",
        f"mealType: {recipe.get('mealType') or ''}",
        f"diet: {recipe.get('diet') or ''}",
        f"cuisine: {recipe.get('cuisine') or ''}",
        f"sourceName: {recipe.get('sourceName') or ''}",
        f"sourceUrl: {recipe.get('sourceUrl') or ''}",
        "",
        "Ingredients:",
    ]
    for ingredient in recipe.get("ingredients") or []:
        if not isinstance(ingredient, Mapping):
            continue
        amount = ingredient.get("amount")
        unit = ingredient.get("unit") or ""
        item = ingredient.get("item") or ""
        prep = ingredient.get("preparation")
        amount_part = f"{amount} {unit}".strip() if amount is not None else ""
        line = f"- {amount_part} {item}".strip()
        if prep:
            line = f"{line} ({prep})"
        lines.append(line)

    lines.append("")
    lines.append("Instructions:")
    for index, instruction in enumerate(recipe.get("instructions") or [], start=1):
        if isinstance(instruction, Mapping):
            step = instruction.get("step", index)
            text = instruction.get("text") or ""
        else:
            step = index
            text = str(instruction)
        if text:
            lines.append(f"{step}. {text}")

    return "\n".join(lines).strip()


class LexicalCatalogRetriever:
    """Score recipes by overlapping query tokens (title/ingredients weighted higher)."""

    def __init__(self, recipes: Sequence[Mapping[str, Any]]):
        self._recipes = [r for r in recipes if isinstance(r, Mapping)]

    def retrieve(
        self,
        query: str,
        *,
        filters: Mapping[str, str] | None = None,
        top_k: int = 8,
    ) -> list[RetrievedChunk]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scored: list[RetrievedChunk] = []
        for recipe in self._recipes:
            if not _filter_matches(recipe, filters):
                continue

            title_tokens = set(_tokenize(str(recipe.get("title") or "")))
            ingredient_tokens = set()
            for ingredient in recipe.get("ingredients") or []:
                if isinstance(ingredient, Mapping):
                    ingredient_tokens.update(_tokenize(str(ingredient.get("item") or "")))

            blob_tokens = set(_tokenize(_recipe_search_blob(recipe)))
            score = 0.0
            for token in query_tokens:
                if token in title_tokens:
                    score += 3.0
                elif token in ingredient_tokens:
                    score += 2.0
                elif token in blob_tokens:
                    score += 1.0

            if score <= 0:
                continue

            scored.append(
                RetrievedChunk(
                    text=_format_recipe_chunk(recipe),
                    score=score,
                    recipe_id=recipe.get("id"),
                    title=recipe.get("title"),
                    source_url=recipe.get("sourceUrl"),
                    source_name=recipe.get("sourceName"),
                    meal_type=recipe.get("mealType"),
                    diet=recipe.get("diet"),
                    cuisine=recipe.get("cuisine"),
                    metadata={"docType": "structured"},
                )
            )

        scored.sort(key=lambda chunk: (-chunk.score, chunk.title or ""))
        return scored[: max(0, top_k)]


class BedrockKnowledgeBaseRetriever:
    """Retrieve chunks from an Amazon Bedrock Knowledge Base."""

    def __init__(
        self,
        knowledge_base_id: str,
        *,
        region: str | None = None,
        client: Any | None = None,
    ):
        if not knowledge_base_id:
            raise ValueError("knowledge_base_id is required.")
        self.knowledge_base_id = knowledge_base_id
        self.region = region or AWS_CONFIG["REGION"]
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        if boto3 is None:
            raise RuntimeError("boto3 is required for Bedrock Knowledge Base retrieval.")
        self._client = boto3.client("bedrock-agent-runtime", region_name=self.region)
        return self._client

    @staticmethod
    def _build_metadata_filter(filters: Mapping[str, str] | None) -> dict[str, Any] | None:
        if not filters:
            return None

        equals_filters = []
        for key, value in filters.items():
            if key not in FILTER_KEYS:
                continue
            if value is None or not str(value).strip():
                continue
            equals_filters.append({"equals": {"key": key, "value": str(value).strip()}})

        if not equals_filters:
            return None
        if len(equals_filters) == 1:
            return equals_filters[0]
        return {"andAll": equals_filters}

    def retrieve(
        self,
        query: str,
        *,
        filters: Mapping[str, str] | None = None,
        top_k: int = 8,
    ) -> list[RetrievedChunk]:
        vector_config: dict[str, Any] = {"numberOfResults": max(1, top_k)}
        metadata_filter = self._build_metadata_filter(filters)
        if metadata_filter is not None:
            vector_config["filter"] = metadata_filter

        response = self._get_client().retrieve(
            knowledgeBaseId=self.knowledge_base_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": vector_config,
            },
        )

        chunks: list[RetrievedChunk] = []
        for result in response.get("retrievalResults") or []:
            content = result.get("content") or {}
            text = content.get("text") or ""
            if not text.strip():
                continue

            metadata = result.get("metadata") or {}
            score = float(result.get("score") or 0.0)
            chunks.append(
                RetrievedChunk(
                    text=text.strip(),
                    score=score,
                    recipe_id=metadata.get("recipeId") or metadata.get("recipe_id"),
                    title=metadata.get("title"),
                    source_url=metadata.get("sourceUrl") or metadata.get("source_url"),
                    source_name=metadata.get("sourceName") or metadata.get("source_name"),
                    meal_type=metadata.get("mealType") or metadata.get("meal_type"),
                    diet=metadata.get("diet"),
                    cuisine=metadata.get("cuisine"),
                    metadata=metadata,
                )
            )
        return chunks


def knowledge_base_id() -> str:
    return os.environ.get("KNOWLEDGE_BASE_ID", "").strip()


def get_retriever(
    recipes: Sequence[Mapping[str, Any]] | None = None,
    *,
    client: Any | None = None,
) -> Retriever:
    kb_id = knowledge_base_id()
    if kb_id:
        return BedrockKnowledgeBaseRetriever(kb_id, client=client)
    return LexicalCatalogRetriever(recipes or [])
