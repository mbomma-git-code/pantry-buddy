import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import sync_kb_index as sync  # noqa: E402


class SyncKbIndexTests(unittest.TestCase):
    def _write_local_corpus(self, root: Path) -> Path:
        structured = root / "structured"
        structured.mkdir(parents=True)
        (structured / "berry-oats.txt").write_text("title: Berry Oats\n", encoding="utf-8")
        (structured / "berry-oats.txt.metadata.json").write_text(
            json.dumps({"metadataAttributes": {"recipeId": "berry-oats"}}) + "\n",
            encoding="utf-8",
        )
        manifest = {
            "version": "1.0",
            "documents": [
                {
                    "recipeId": "berry-oats",
                    "filename": "berry-oats.txt",
                    "contentSha256": "abc123",
                    "sourceUrl": "https://example.test/berry-oats",
                }
            ],
        }
        (root / "kb_manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
        return root

    def test_upsert_uploads_changed_and_deletes_orphans(self):
        with tempfile.TemporaryDirectory() as tmp:
            local_dir = self._write_local_corpus(Path(tmp))
            s3 = MagicMock()

            # No remote manifest -> treat as new
            class FakeClientError(Exception):
                def __init__(self):
                    self.response = {"Error": {"Code": "NoSuchKey"}}

            # Match sync module's ClientError type used in except clauses.
            sync.ClientError = FakeClientError  # type: ignore[misc,assignment]
            s3.get_object.side_effect = FakeClientError()

            # Remote has an orphaned object
            s3.get_paginator.return_value.paginate.return_value = [
                {
                    "Contents": [
                        {"Key": "kb/structured/old-recipe.txt"},
                        {"Key": "kb/structured/old-recipe.txt.metadata.json"},
                        {"Key": "kb/structured/.gitkeep"},
                    ]
                }
            ]

            summary = sync.sync_structured_corpus(
                s3_client=s3,
                bucket="data-bucket",
                local_dir=local_dir,
                prefix="kb/structured/",
            )

            uploaded_keys = [call.args[2] for call in s3.upload_file.call_args_list]
            self.assertIn("kb/structured/berry-oats.txt", uploaded_keys)
            self.assertIn("kb/structured/berry-oats.txt.metadata.json", uploaded_keys)

            deleted_keys = [c.kwargs["Key"] for c in s3.delete_object.call_args_list]
            self.assertIn("kb/structured/old-recipe.txt", deleted_keys)
            self.assertIn("kb/structured/old-recipe.txt.metadata.json", deleted_keys)
            self.assertNotIn("kb/structured/.gitkeep", deleted_keys)

            put_keys = [c.kwargs["Key"] for c in s3.put_object.call_args_list]
            self.assertIn(sync.REMOTE_MANIFEST_KEY, put_keys)
            self.assertEqual(summary["documentCount"], 1)

    def test_skip_unchanged_when_hashes_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            local_dir = self._write_local_corpus(Path(tmp))
            s3 = MagicMock()
            remote_manifest = {
                "documents": [
                    {
                        "recipeId": "berry-oats",
                        "filename": "berry-oats.txt",
                        "contentSha256": "abc123",
                    }
                ]
            }
            s3.get_object.return_value = {
                "Body": MagicMock(read=lambda: json.dumps(remote_manifest).encode("utf-8"))
            }
            s3.get_paginator.return_value.paginate.return_value = [
                {
                    "Contents": [
                        {"Key": "kb/structured/berry-oats.txt"},
                        {"Key": "kb/structured/berry-oats.txt.metadata.json"},
                    ]
                }
            ]

            summary = sync.sync_structured_corpus(
                s3_client=s3,
                bucket="data-bucket",
                local_dir=local_dir,
            )

            self.assertEqual(s3.upload_file.call_count, 0)
            self.assertEqual(summary["uploaded"], [])
            self.assertEqual(s3.put_object.call_count, 1)

    def test_start_ingestion_returns_job_id(self):
        client = MagicMock()
        client.start_ingestion_job.return_value = {
            "ingestionJob": {"ingestionJobId": "job-1", "status": "STARTING"}
        }
        result = sync.start_ingestion(
            bedrock_agent_client=client,
            knowledge_base_id="kb-1",
            data_source_id="ds-1",
        )
        self.assertEqual(result["ingestionJobId"], "job-1")
        client.start_ingestion_job.assert_called_once()


if __name__ == "__main__":
    unittest.main()
