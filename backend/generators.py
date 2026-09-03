"""
Answer generation for PantryBuddy v3 chat.

Modes (RAG_GENERATOR):
  - auto (default): Bedrock Claude when available, else extract
  - bedrock: always InvokeModel
  - extract: deterministic grounded answer from retrieved chunks (no LLM)
  - fake: fixed answer for unit tests
"""

from __future__ import annotations

import json
import os
from typing import Any, Mapping, Sequence

try:
    import boto3  # pyright: ignore[reportMissingImports]
except ImportError:
    boto3 = None

from config import AWS_CONFIG, RAG_CONFIG, DEFAULT_GENERATOR_MODEL_ID
from retrievers import RetrievedChunk

SYSTEM_PROMPT = """You are PantryBuddy's recipe assistant.
Use ONLY the retrieved catalog context for factual recipe claims (titles, ingredients, amounts, steps, sources).
If the context is insufficient, say so clearly and do not invent recipes or sources.
General cooking knowledge may be offered only when clearly labeled as not from the catalog.
When you reference a specific recipe, mention its title and source name when available.
Keep answers concise and practical."""


def _generator_mode() -> str:
    return os.environ.get("RAG_GENERATOR", RAG_CONFIG.get("GENERATOR_MODE", "auto")).strip().lower()


def _model_id() -> str:
    return os.environ.get(
        "GENERATOR_MODEL_ID",
        RAG_CONFIG.get("GENERATOR_MODEL_ID", DEFAULT_GENERATOR_MODEL_ID),
    )


def format_context_block(chunks: Sequence[RetrievedChunk]) -> str:
    blocks = []
    for index, chunk in enumerate(chunks, start=1):
        header = f"[Chunk {index}]"
        meta_bits = []
        if chunk.recipe_id:
            meta_bits.append(f"recipeId={chunk.recipe_id}")
        if chunk.title:
            meta_bits.append(f"title={chunk.title}")
        if chunk.source_name:
            meta_bits.append(f"sourceName={chunk.source_name}")
        if chunk.source_url:
            meta_bits.append(f"sourceUrl={chunk.source_url}")
        if meta_bits:
            header = f"{header} ({', '.join(meta_bits)})"
        blocks.append(f"{header}\n{chunk.text}")
    return "\n\n".join(blocks)


def extract_generate(
    messages: Sequence[Mapping[str, str]],
    chunks: Sequence[RetrievedChunk],
) -> str:
    """Deterministic grounded answer used when no LLM is available."""
    if not chunks:
        return ""

    query = ""
    for message in reversed(messages):
        if message.get("role") == "user":
            query = str(message.get("content") or "").strip()
            break

    lines = [
        f"Based on the PantryBuddy catalog, here is grounded context for: {query or 'your question'}.",
        "",
    ]
    for chunk in chunks[:5]:
        title = chunk.title or chunk.recipe_id or "Recipe"
        source = chunk.source_name or "Unknown source"
        lines.append(f"- {title} ({source})")
        preview = " ".join(chunk.text.split())
        if len(preview) > 280:
            preview = preview[:277] + "..."
        lines.append(f"  Excerpt: {preview}")
        if chunk.source_url:
            lines.append(f"  Source: {chunk.source_url}")
        lines.append("")

    lines.append(
        "Use the cited sources above for exact ingredients and steps. "
        "I am not inventing recipes outside this retrieved context."
    )
    return "\n".join(lines).strip()


def fake_generate(
    messages: Sequence[Mapping[str, str]],
    chunks: Sequence[RetrievedChunk],
) -> str:
    titles = [chunk.title or chunk.recipe_id or "recipe" for chunk in chunks]
    return "FAKE_ANSWER grounded in: " + ", ".join(titles)


def invoke_claude(
    messages: Sequence[Mapping[str, str]],
    chunks: Sequence[RetrievedChunk],
    *,
    client: Any | None = None,
) -> str:
    if boto3 is None and client is None:
        raise RuntimeError("boto3 is required for Bedrock generation.")

    bedrock = client or boto3.client(
        "bedrock-runtime",
        region_name=AWS_CONFIG["REGION"],
    )

    context = format_context_block(chunks)
    user_transcript = []
    for message in messages:
        role = message.get("role")
        content = str(message.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        user_transcript.append({"role": role, "content": content})

    if not user_transcript:
        raise ValueError("At least one chat message is required.")

    # Attach retrieved context to the latest user turn.
    last = user_transcript[-1]
    if last["role"] == "user":
        last = {
            "role": "user",
            "content": (
                f"{last['content']}\n\n"
                f"Retrieved catalog context:\n{context}"
            ),
        }
        user_transcript = user_transcript[:-1] + [last]

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": int(RAG_CONFIG.get("MAX_TOKENS", 1024)),
        "temperature": float(RAG_CONFIG.get("TEMPERATURE", 0.2)),
        "system": SYSTEM_PROMPT,
        "messages": user_transcript,
    }

    response = bedrock.invoke_model(
        modelId=_model_id(),
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    payload = json.loads(response["body"].read())
    parts = []
    for block in payload.get("content") or []:
        if isinstance(block, Mapping) and block.get("type") == "text":
            parts.append(str(block.get("text") or ""))
    answer = "\n".join(part for part in parts if part).strip()
    if not answer:
        raise RuntimeError("Bedrock returned an empty generation.")
    return answer


def generate_chat_answer(
    messages: Sequence[Mapping[str, str]],
    chunks: Sequence[RetrievedChunk],
    *,
    client: Any | None = None,
) -> str:
    mode = _generator_mode()

    if mode == "fake":
        return fake_generate(messages, chunks)
    if mode == "extract":
        return extract_generate(messages, chunks)
    if mode == "bedrock":
        return invoke_claude(messages, chunks, client=client)

    # auto
    try:
        return invoke_claude(messages, chunks, client=client)
    except Exception:
        return extract_generate(messages, chunks)
