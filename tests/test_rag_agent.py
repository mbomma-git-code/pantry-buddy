import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import rag_agent  # noqa: E402
from retrievers import (  # noqa: E402
    BedrockKnowledgeBaseRetriever,
    LexicalCatalogRetriever,
    RetrievedChunk,
    get_retriever,
)
from v3_api_contract import LOW_RECALL_ANSWER  # noqa: E402


RECIPES = [
    {
        "id": "berry-oats",
        "title": "Berry Oats",
        "mealType": "breakfast",
        "diet": "vegetarian",
        "cuisine": "American",
        "sourceName": "Pantry Buddy Test Kitchen",
        "sourceUrl": "https://example.test/berry-oats",
        "ingredients": [{"item": "Oats", "amount": 1, "unit": "cup", "preparation": None}],
        "instructions": [{"step": 1, "text": "Cook the oats with berries."}],
    },
    {
        "id": "lentil-soup",
        "title": "Lentil Soup",
        "mealType": "dinner",
        "diet": "vegan",
        "cuisine": "Middle Eastern",
        "sourceName": "Dinner Desk",
        "sourceUrl": "https://example.test/lentil-soup",
        "ingredients": [{"item": "Lentils", "amount": 2, "unit": "cups", "preparation": None}],
        "instructions": [{"step": 1, "text": "Simmer until tender."}],
    },
]


class RagAgentTests(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {"RAG_GENERATOR": "fake", "KNOWLEDGE_BASE_ID": ""})
        self._env.start()
        importlib.reload(rag_agent)

    def tearDown(self):
        self._env.stop()

    def test_lexical_retriever_prefers_title_matches(self):
        retriever = LexicalCatalogRetriever(RECIPES)
        chunks = retriever.retrieve("berry oats breakfast", top_k=2)
        self.assertTrue(chunks)
        self.assertEqual(chunks[0].recipe_id, "berry-oats")

    def test_lexical_retriever_applies_filters(self):
        retriever = LexicalCatalogRetriever(RECIPES)
        chunks = retriever.retrieve("soup lentils", filters={"mealType": "breakfast"}, top_k=5)
        self.assertEqual(chunks, [])

    def test_run_chat_returns_citations(self):
        payload = rag_agent.run_chat(
            {"messages": [{"role": "user", "content": "How do I make berry oats?"}]},
            RECIPES,
        )
        self.assertIn("Berry Oats", payload["answer"])
        self.assertEqual(payload["citations"][0]["recipeId"], "berry-oats")
        self.assertEqual(payload["citations"][0]["sourceUrl"], "https://example.test/berry-oats")

    def test_run_chat_low_recall(self):
        payload = rag_agent.run_chat(
            {"messages": [{"role": "user", "content": "xyzzyplugh"}]},
            RECIPES,
        )
        self.assertEqual(payload["answer"], LOW_RECALL_ANSWER)
        self.assertEqual(payload["citations"], [])

    def test_bedrock_retriever_maps_metadata(self):
        client = MagicMock()
        client.retrieve.return_value = {
            "retrievalResults": [
                {
                    "content": {"text": "title: Berry Oats\nIngredients:\n- oats"},
                    "score": 0.91,
                    "metadata": {
                        "recipeId": "berry-oats",
                        "title": "Berry Oats",
                        "sourceUrl": "https://example.test/berry-oats",
                        "sourceName": "Pantry Buddy Test Kitchen",
                        "mealType": "breakfast",
                    },
                }
            ]
        }
        retriever = BedrockKnowledgeBaseRetriever("kb-123", client=client)
        chunks = retriever.retrieve("berry oats", filters={"mealType": "breakfast"}, top_k=3)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].recipe_id, "berry-oats")
        client.retrieve.assert_called_once()
        kwargs = client.retrieve.call_args.kwargs
        self.assertEqual(kwargs["knowledgeBaseId"], "kb-123")
        self.assertIn("filter", kwargs["retrievalConfiguration"]["vectorSearchConfiguration"])

    def test_bedrock_retriever_ignores_unknown_filter_keys(self):
        client = MagicMock()
        client.retrieve.return_value = {"retrievalResults": []}
        retriever = BedrockKnowledgeBaseRetriever("kb-123", client=client)
        retriever.retrieve(
            "oats",
            filters={"mealType": "breakfast", "unknownKey": "nope"},
            top_k=2,
        )
        vector_config = client.retrieve.call_args.kwargs["retrievalConfiguration"][
            "vectorSearchConfiguration"
        ]
        self.assertEqual(
            vector_config["filter"],
            {"equals": {"key": "mealType", "value": "breakfast"}},
        )

    def test_get_retriever_uses_bedrock_when_kb_configured(self):
        client = MagicMock()
        client.retrieve.return_value = {"retrievalResults": []}
        with patch.dict(os.environ, {"KNOWLEDGE_BASE_ID": "kb-prod"}, clear=False):
            retriever = get_retriever(RECIPES, client=client)
        self.assertIsInstance(retriever, BedrockKnowledgeBaseRetriever)
        retriever.retrieve("anything", top_k=1)
        client.retrieve.assert_called_once()

    def test_run_chat_uses_injected_retriever(self):
        class FixedRetriever:
            def retrieve(self, query, *, filters=None, top_k=8):
                return [
                    RetrievedChunk(
                        text="title: Lentil Soup\nInstructions:\n1. Simmer.",
                        score=1.0,
                        recipe_id="lentil-soup",
                        title="Lentil Soup",
                        source_url="https://example.test/lentil-soup",
                        source_name="Dinner Desk",
                    )
                ]

        payload = rag_agent.run_chat(
            {"messages": [{"role": "user", "content": "dinner ideas"}]},
            RECIPES,
            retriever=FixedRetriever(),
        )
        self.assertEqual(payload["citations"][0]["recipeId"], "lentil-soup")

    def test_run_suggest_meals_hydrates_from_catalog(self):
        payload = rag_agent.run_suggest_meals(
            {
                "query": "berry oats breakfast",
                "count": 1,
                "filters": {"mealType": "breakfast"},
            },
            RECIPES,
        )
        self.assertEqual(len(payload["suggestions"]), 1)
        self.assertEqual(payload["suggestions"][0]["id"], "berry-oats")
        self.assertEqual(
            payload["suggestions"][0]["ingredients"][0]["item"], "Oats"
        )
        self.assertEqual(payload["citations"][0]["recipeId"], "berry-oats")


if __name__ == "__main__":
    unittest.main()
