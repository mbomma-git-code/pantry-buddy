import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from v3_api_contract import (  # noqa: E402
    CONTRACT_VERSION,
    validate_v3_chat_request,
    validate_v3_suggest_meals_request,
)


class V3ApiContractTests(unittest.TestCase):
    def test_chat_accepts_minimal_valid_body(self):
        validate_v3_chat_request(
            {"messages": [{"role": "user", "content": "What can I substitute for paneer?"}]}
        )

    def test_chat_rejects_missing_user_message(self):
        with self.assertRaises(ValueError) as ctx:
            validate_v3_chat_request(
                {"messages": [{"role": "assistant", "content": "Hello."}]}
            )
        self.assertIn("user message", str(ctx.exception).lower())

    def test_chat_validates_filters_and_retrieval(self):
        validate_v3_chat_request(
            {
                "messages": [{"role": "user", "content": "Quick vegan snack?"}],
                "filters": {"mealType": "snack", "diet": "vegan"},
                "retrieval": {"corpusPreference": "structured", "topK": 10},
            }
        )

    def test_chat_rejects_bad_corpus_preference(self):
        with self.assertRaises(ValueError) as ctx:
            validate_v3_chat_request(
                {
                    "messages": [{"role": "user", "content": "Hi"}],
                    "retrieval": {"corpusPreference": "invalid"},
                }
            )
        self.assertIn("corpusPreference", str(ctx.exception))

    def test_suggest_accepts_minimal_valid_body(self):
        validate_v3_suggest_meals_request({"query": "high protein vegetarian dinners"})

    def test_suggest_rejects_empty_query(self):
        with self.assertRaises(ValueError):
            validate_v3_suggest_meals_request({"query": "  "})

    def test_suggest_validates_count_bounds(self):
        with self.assertRaises(ValueError):
            validate_v3_suggest_meals_request({"query": "x", "count": 99})

    def test_contract_version_is_semverish(self):
        self.assertRegex(CONTRACT_VERSION, r"^\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
