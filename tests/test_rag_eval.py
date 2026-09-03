"""
RAG v3 quality eval: golden-query recall + citation attribution checks.

Uses the local lexical catalog retriever (no AWS). Re-run against Bedrock KB
manually when validating production retrieval quality.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import rag_agent  # noqa: E402
from retrievers import LexicalCatalogRetriever  # noqa: E402
from v3_api_contract import LOW_RECALL_ANSWER  # noqa: E402

GOLDEN_PATH = REPO_ROOT / "data" / "kb" / "golden_queries.json"
RECIPES_PATH = REPO_ROOT / "data" / "recipes_json" / "recipes.json"

REQUIRED_CITATION_KEYS = ("sourceUrl", "sourceName", "excerpt")


def _load_recipes() -> list[dict]:
    payload = json.loads(RECIPES_PATH.read_text(encoding="utf-8"))
    recipes = payload.get("recipes") if isinstance(payload, dict) else payload
    if not isinstance(recipes, list) or not recipes:
        raise AssertionError(f"No recipes found in {RECIPES_PATH}")
    return [r for r in recipes if isinstance(r, dict)]


def _load_golden() -> dict:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def _recipe_index(recipes: list[dict]) -> dict[str, dict]:
    return {str(r["id"]): r for r in recipes if r.get("id")}


class RagEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipes = _load_recipes()
        cls.by_id = _recipe_index(cls.recipes)
        cls.golden = _load_golden()
        cls.cases = cls.golden.get("cases") or []
        cls.default_top_k = int((cls.golden.get("defaults") or {}).get("topK", 5))
        if not cls.cases:
            raise AssertionError(f"No golden cases in {GOLDEN_PATH}")

    def setUp(self):
        self._env = patch.dict(
            os.environ,
            {"RAG_GENERATOR": "extract", "KNOWLEDGE_BASE_ID": ""},
        )
        self._env.start()
        importlib.reload(rag_agent)
        self.retriever = LexicalCatalogRetriever(self.recipes)

    def tearDown(self):
        self._env.stop()

    def test_golden_file_references_known_recipe_ids(self):
        for case in self.cases:
            expect = case.get("expect") or {}
            for key in ("mustIncludeRecipeIds", "mustExcludeRecipeIds"):
                for recipe_id in expect.get(key) or []:
                    self.assertIn(
                        recipe_id,
                        self.by_id,
                        f"Golden case {case.get('id')}: unknown recipe id {recipe_id}",
                    )

    def test_golden_recall(self):
        failures: list[str] = []
        for case in self.cases:
            case_id = case.get("id", "<missing-id>")
            query = case.get("query") or ""
            filters = case.get("filters")
            expect = case.get("expect") or {}
            top_k = int(expect.get("topK", self.default_top_k))

            chunks = self.retriever.retrieve(query, filters=filters, top_k=top_k)
            retrieved_ids = [c.recipe_id for c in chunks if c.recipe_id]

            if expect.get("lowRecall"):
                if chunks:
                    failures.append(
                        f"{case_id}: expected low recall, got {retrieved_ids}"
                    )
                continue

            for recipe_id in expect.get("mustIncludeRecipeIds") or []:
                if recipe_id not in retrieved_ids:
                    failures.append(
                        f"{case_id}: missing {recipe_id} in top-{top_k} {retrieved_ids}"
                    )
                    continue
                rank_at_most = expect.get("rankAtMost")
                if rank_at_most is not None:
                    rank = retrieved_ids.index(recipe_id) + 1
                    if rank > int(rank_at_most):
                        failures.append(
                            f"{case_id}: {recipe_id} at rank {rank}, "
                            f"wanted <= {rank_at_most}"
                        )

            for recipe_id in expect.get("mustExcludeRecipeIds") or []:
                if recipe_id in retrieved_ids:
                    failures.append(
                        f"{case_id}: unexpectedly retrieved {recipe_id}"
                    )

        self.assertEqual(failures, [], msg="\n".join(failures))

    def test_golden_citation_attribution(self):
        failures: list[str] = []
        for case in self.cases:
            case_id = case.get("id", "<missing-id>")
            expect = case.get("expect") or {}
            if expect.get("lowRecall"):
                payload = rag_agent.run_chat(
                    {"messages": [{"role": "user", "content": case["query"]}]},
                    self.recipes,
                    retriever=self.retriever,
                )
                if payload.get("answer") != LOW_RECALL_ANSWER:
                    failures.append(f"{case_id}: expected LOW_RECALL_ANSWER")
                if payload.get("citations"):
                    failures.append(f"{case_id}: expected empty citations")
                continue

            if not expect.get("requireCitations"):
                continue

            body: dict = {
                "messages": [{"role": "user", "content": case["query"]}],
                "retrieval": {"topK": int(expect.get("topK", self.default_top_k))},
            }
            if case.get("filters"):
                body["filters"] = case["filters"]

            payload = rag_agent.run_chat(
                body, self.recipes, retriever=self.retriever
            )
            citations = payload.get("citations") or []
            if not citations:
                failures.append(f"{case_id}: expected citations, got none")
                continue

            for citation in citations:
                for key in REQUIRED_CITATION_KEYS:
                    if key not in citation:
                        failures.append(f"{case_id}: citation missing {key}")

                recipe_id = citation.get("recipeId")
                if not recipe_id:
                    failures.append(f"{case_id}: citation missing recipeId")
                    continue
                catalog = self.by_id.get(recipe_id)
                if catalog is None:
                    failures.append(
                        f"{case_id}: citation recipeId {recipe_id} not in catalog"
                    )
                    continue

                expected_url = catalog.get("sourceUrl") or ""
                expected_name = catalog.get("sourceName") or ""
                if citation.get("sourceUrl") != expected_url:
                    failures.append(
                        f"{case_id}: sourceUrl mismatch for {recipe_id}: "
                        f"{citation.get('sourceUrl')!r} != {expected_url!r}"
                    )
                if citation.get("sourceName") != expected_name:
                    failures.append(
                        f"{case_id}: sourceName mismatch for {recipe_id}: "
                        f"{citation.get('sourceName')!r} != {expected_name!r}"
                    )

            for recipe_id in expect.get("mustIncludeRecipeIds") or []:
                cited_ids = [c.get("recipeId") for c in citations]
                if recipe_id not in cited_ids:
                    failures.append(
                        f"{case_id}: expected citation for {recipe_id}, got {cited_ids}"
                    )

            if LOW_RECALL_ANSWER in str(payload.get("answer") or ""):
                failures.append(f"{case_id}: answer looked like low-recall")

        self.assertEqual(failures, [], msg="\n".join(failures))

    def test_build_citations_dedupes_and_truncates(self):
        from retrievers import RetrievedChunk

        chunks = [
            RetrievedChunk(
                text="x" * 400,
                score=1.0,
                recipe_id="a",
                title="A",
                source_url="https://example.test/a",
                source_name="Source A",
            ),
            RetrievedChunk(
                text="second hit same recipe",
                score=0.5,
                recipe_id="a",
                title="A",
                source_url="https://example.test/a",
                source_name="Source A",
            ),
        ]
        citations = rag_agent.build_citations(chunks)
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]["recipeId"], "a")
        self.assertEqual(citations[0]["sourceUrl"], "https://example.test/a")
        self.assertEqual(citations[0]["sourceName"], "Source A")
        self.assertLessEqual(len(citations[0]["excerpt"]), 220)


if __name__ == "__main__":
    unittest.main()
