#!/usr/bin/env python3
"""
Build Bedrock Knowledge Base Corpus A documents from the canonical recipe artifact.

Writes:
  {output_dir}/structured/{recipe_id}.txt
  {output_dir}/structured/{recipe_id}.txt.metadata.json
  {output_dir}/kb_manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping


DEFAULT_MAX_BODY_BYTES = 40_000


def load_recipes(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        artifact = json.load(handle)

    if not isinstance(artifact, dict):
        raise ValueError("Canonical artifact must be a JSON object.")

    recipes = artifact.get("recipes")
    if not isinstance(recipes, list) or not recipes:
        raise ValueError("Canonical artifact must include a non-empty 'recipes' list.")

    normalized = []
    for recipe in recipes:
        if not isinstance(recipe, dict):
            raise ValueError("Each recipe must be an object.")
        recipe_id = recipe.get("id")
        if not isinstance(recipe_id, str) or not recipe_id.strip():
            raise ValueError("Each recipe must include a non-empty string 'id'.")
        normalized.append(recipe)

    return artifact, normalized


def render_recipe_body(recipe: Mapping[str, Any]) -> str:
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
        preparation = ingredient.get("preparation")
        amount_part = f"{amount} {unit}".strip() if amount is not None else ""
        line = f"- {amount_part} {item}".strip()
        if preparation:
            line = f"{line} ({preparation})"
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

    nutrition = recipe.get("nutrition")
    if isinstance(nutrition, Mapping) and any(v is not None for v in nutrition.values()):
        lines.append("")
        parts = []
        for key in ("calories", "proteinGrams", "carbsGrams", "fatGrams"):
            if nutrition.get(key) is not None:
                parts.append(f"{key}={nutrition.get(key)}")
        if parts:
            lines.append("Nutrition: " + ", ".join(parts))

    return "\n".join(lines).rstrip() + "\n"


def split_body(body: str, recipe_id: str, max_body_bytes: int) -> list[tuple[str, str]]:
    encoded = body.encode("utf-8")
    if len(encoded) <= max_body_bytes:
        return [(f"{recipe_id}.txt", body)]

    # Prefer splitting on blank lines; fall back to hard byte windows.
    paragraphs = body.split("\n\n")
    parts: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate.encode("utf-8")) <= max_body_bytes:
            current = candidate
            continue
        if current:
            parts.append(current)
        if len(paragraph.encode("utf-8")) <= max_body_bytes:
            current = paragraph
        else:
            raw = paragraph.encode("utf-8")
            for start in range(0, len(raw), max_body_bytes):
                chunk = raw[start : start + max_body_bytes].decode("utf-8", errors="ignore")
                if chunk:
                    parts.append(chunk)
            current = ""
    if current:
        parts.append(current)

    if not parts:
        parts = [body]

    total = len(parts)
    return [
        (f"{recipe_id}-p{index:02d}.txt", part if part.endswith("\n") else part + "\n")
        for index, part in enumerate(parts, start=1)
    ]


def metadata_for_recipe(
    recipe: Mapping[str, Any],
    *,
    artifact: Mapping[str, Any],
    content_sha256: str,
    chunk_part: int | None = None,
    chunk_parts_total: int | None = None,
) -> dict[str, Any]:
    attributes: dict[str, Any] = {
        "docType": "structured",
        "recipeId": recipe.get("id"),
        "sourceUrl": recipe.get("sourceUrl") or "",
        "sourceName": recipe.get("sourceName"),
        "title": recipe.get("title"),
        "mealType": recipe.get("mealType"),
        "diet": recipe.get("diet"),
        "cuisine": recipe.get("cuisine"),
        "artifactGeneratedAt": artifact.get("generatedAt"),
        "artifactVersion": artifact.get("version"),
        "contentSha256": content_sha256,
    }
    if chunk_part is not None:
        attributes["chunkPart"] = chunk_part
        attributes["chunkPartsTotal"] = chunk_parts_total
    return {"metadataAttributes": attributes}


def build_index(
    *,
    input_path: Path,
    output_dir: Path,
    rebuild: bool = False,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
) -> dict[str, Any]:
    artifact, recipes = load_recipes(input_path)
    structured_dir = output_dir / "structured"

    if rebuild and structured_dir.exists():
        shutil.rmtree(structured_dir)
    structured_dir.mkdir(parents=True, exist_ok=True)
    gitkeep = structured_dir / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("", encoding="utf-8")

    manifest_entries: list[dict[str, Any]] = []
    keep_names: set[str] = set()

    for recipe in recipes:
        recipe_id = str(recipe["id"])
        body = render_recipe_body(recipe)
        parts = split_body(body, recipe_id, max_body_bytes)
        total_parts = len(parts)

        for index, (filename, part_body) in enumerate(parts, start=1):
            content_sha = hashlib.sha256(part_body.encode("utf-8")).hexdigest()
            body_path = structured_dir / filename
            meta_name = f"{filename}.metadata.json"
            meta_path = structured_dir / meta_name

            body_path.write_text(part_body, encoding="utf-8")
            metadata = metadata_for_recipe(
                recipe,
                artifact=artifact,
                content_sha256=content_sha,
                chunk_part=index if total_parts > 1 else None,
                chunk_parts_total=total_parts if total_parts > 1 else None,
            )
            meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

            keep_names.add(filename)
            keep_names.add(meta_name)
            manifest_entries.append(
                {
                    "recipeId": recipe_id,
                    "filename": filename,
                    "contentSha256": content_sha,
                    "sourceUrl": recipe.get("sourceUrl"),
                }
            )

    # Orphan cleanup when not doing a full rebuild wipe.
    for existing in structured_dir.iterdir():
        if existing.name in {".gitkeep", ".gitignore"}:
            continue
        if existing.name not in keep_names and existing.is_file():
            existing.unlink()

    manifest = {
        "version": "1.0",
        "generatedFrom": str(input_path),
        "artifactGeneratedAt": artifact.get("generatedAt"),
        "artifactVersion": artifact.get("version"),
        "documents": manifest_entries,
    }
    manifest_path = output_dir / "kb_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=repo_root / "data" / "recipes_json" / "recipes.json",
        help="Canonical recipes.json path",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repo_root / "data" / "kb",
        help="Output directory for structured docs and manifest",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete structured/ before writing",
    )
    parser.add_argument(
        "--max-body-bytes",
        type=int,
        default=DEFAULT_MAX_BODY_BYTES,
        help="Split documents larger than this many UTF-8 bytes",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = build_index(
        input_path=args.input,
        output_dir=args.output_dir,
        rebuild=args.rebuild,
        max_body_bytes=args.max_body_bytes,
    )
    print(
        f"Wrote {len(manifest['documents'])} structured document(s) to {args.output_dir / 'structured'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
