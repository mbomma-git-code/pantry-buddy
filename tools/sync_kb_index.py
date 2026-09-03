#!/usr/bin/env python3
"""
Upload Corpus A (data/kb/structured) to S3 and start a Bedrock Knowledge Base ingestion job.

Uses kb_manifest.json content hashes for upsert/delete (full sync supported via --full).

Examples:
  python3 tools/sync_kb_index.py --bucket "$DATA_BUCKET" \\
    --knowledge-base-id "$KB_ID" --data-source-id "$DS_ID"

  make sync-kb-index DATA_BUCKET=... KNOWLEDGE_BASE_ID=... DATA_SOURCE_ID=...
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[misc,assignment]


REMOTE_MANIFEST_KEY = "kb/kb_manifest.json"
DEFAULT_PREFIX = "kb/structured/"


def load_local_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing local manifest at {path}. Run tools/build_kb_index.py first."
        )
    with path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("documents"), list):
        raise ValueError("kb_manifest.json must be an object with a 'documents' list.")
    return manifest


def load_remote_manifest(s3_client: Any, bucket: str, key: str) -> dict[str, Any] | None:
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise
    body = response["Body"].read().decode("utf-8")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        return None
    return payload


def documents_by_filename(manifest: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not manifest:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for entry in manifest.get("documents") or []:
        if not isinstance(entry, dict):
            continue
        filename = entry.get("filename")
        if isinstance(filename, str) and filename:
            out[filename] = entry
    return out


def list_structured_keys(s3_client: Any, bucket: str, prefix: str) -> set[str]:
    keys: set[str] = set()
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents") or []:
            key = obj.get("Key")
            if isinstance(key, str) and key and not key.endswith("/"):
                keys.add(key)
    return keys


def sync_structured_corpus(
    *,
    s3_client: Any,
    bucket: str,
    local_dir: Path,
    prefix: str = DEFAULT_PREFIX,
    full: bool = False,
) -> dict[str, Any]:
    """
    Upsert changed structured docs + metadata sidecars; delete orphans; upload manifest.

    Returns a summary dict with uploaded/deleted counts.
    """
    structured_dir = local_dir / "structured"
    if not structured_dir.is_dir():
        raise FileNotFoundError(f"Missing structured directory: {structured_dir}")

    local_manifest = load_local_manifest(local_dir / "kb_manifest.json")
    remote_manifest = None if full else load_remote_manifest(s3_client, bucket, REMOTE_MANIFEST_KEY)

    local_docs = documents_by_filename(local_manifest)
    remote_docs = documents_by_filename(remote_manifest)

    uploaded: list[str] = []
    deleted: list[str] = []

    for filename, entry in local_docs.items():
        body_path = structured_dir / filename
        meta_name = f"{filename}.metadata.json"
        meta_path = structured_dir / meta_name
        if not body_path.is_file():
            raise FileNotFoundError(f"Manifest references missing file: {body_path}")
        if not meta_path.is_file():
            raise FileNotFoundError(f"Missing metadata sidecar: {meta_path}")

        remote_entry = remote_docs.get(filename)
        changed = (
            full
            or remote_entry is None
            or remote_entry.get("contentSha256") != entry.get("contentSha256")
        )
        if not changed:
            continue

        body_key = f"{prefix}{filename}"
        meta_key = f"{prefix}{meta_name}"
        s3_client.upload_file(str(body_path), bucket, body_key)
        s3_client.upload_file(
            str(meta_path),
            bucket,
            meta_key,
            ExtraArgs={"ContentType": "application/json"},
        )
        uploaded.extend([body_key, meta_key])

    keep_keys = set()
    for filename in local_docs:
        keep_keys.add(f"{prefix}{filename}")
        keep_keys.add(f"{prefix}{filename}.metadata.json")

    remote_keys = list_structured_keys(s3_client, bucket, prefix)
    for key in sorted(remote_keys - keep_keys):
        # Ignore placeholder / non-corpus objects under the prefix.
        name = key[len(prefix) :] if key.startswith(prefix) else key
        if name in {".gitkeep", "README.md"}:
            continue
        s3_client.delete_object(Bucket=bucket, Key=key)
        deleted.append(key)

    manifest_bytes = json.dumps(local_manifest, indent=2) + "\n"
    s3_client.put_object(
        Bucket=bucket,
        Key=REMOTE_MANIFEST_KEY,
        Body=manifest_bytes.encode("utf-8"),
        ContentType="application/json",
    )

    return {
        "uploaded": uploaded,
        "deleted": deleted,
        "documentCount": len(local_docs),
        "manifestKey": REMOTE_MANIFEST_KEY,
    }


def start_ingestion(
    *,
    bedrock_agent_client: Any,
    knowledge_base_id: str,
    data_source_id: str,
    description: str = "PantryBuddy structured corpus sync",
) -> dict[str, Any]:
    response = bedrock_agent_client.start_ingestion_job(
        knowledgeBaseId=knowledge_base_id,
        dataSourceId=data_source_id,
        description=description[:200],
    )
    job = response.get("ingestionJob") or {}
    return {
        "ingestionJobId": job.get("ingestionJobId"),
        "status": job.get("status"),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--local-dir",
        type=Path,
        default=repo_root / "data" / "kb",
        help="Local KB output directory (contains structured/ and kb_manifest.json)",
    )
    parser.add_argument("--bucket", required=True, help="Data bucket name (DataBucketName output)")
    parser.add_argument(
        "--prefix",
        default=DEFAULT_PREFIX,
        help="S3 key prefix for structured docs (default: kb/structured/)",
    )
    parser.add_argument(
        "--knowledge-base-id",
        default="",
        help="Bedrock Knowledge Base ID (stack output KnowledgeBaseId)",
    )
    parser.add_argument(
        "--data-source-id",
        default="",
        help="Bedrock data source ID (stack output KnowledgeBaseDataSourceId)",
    )
    parser.add_argument(
        "--region",
        default=None,
        help="AWS region (default: AWS_REGION / us-east-2)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Re-upload every document regardless of content hash",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Upload/delete only; do not start an ingestion job",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if boto3 is None:
        print("boto3 is required. Install AWS SDK dependencies and retry.", file=sys.stderr)
        return 2

    args = parse_args(argv)
    prefix = args.prefix if args.prefix.endswith("/") else f"{args.prefix}/"
    region = args.region or __import__("os").environ.get("AWS_REGION", "us-east-2")

    s3_client = boto3.client("s3", region_name=region)
    summary = sync_structured_corpus(
        s3_client=s3_client,
        bucket=args.bucket,
        local_dir=args.local_dir,
        prefix=prefix,
        full=args.full,
    )
    print(
        f"Synced {summary['documentCount']} document(s): "
        f"uploaded={len(summary['uploaded'])} deleted={len(summary['deleted'])}"
    )
    for key in summary["uploaded"]:
        print(f"  + {key}")
    for key in summary["deleted"]:
        print(f"  - {key}")

    if args.skip_ingest:
        print("Skipped ingestion (--skip-ingest).")
        return 0

    if not args.knowledge_base_id or not args.data_source_id:
        print(
            "Upload complete. Pass --knowledge-base-id and --data-source-id to start ingestion, "
            "or re-run without --skip-ingest once those IDs are known.",
            file=sys.stderr,
        )
        return 0

    bedrock = boto3.client("bedrock-agent", region_name=region)
    job = start_ingestion(
        bedrock_agent_client=bedrock,
        knowledge_base_id=args.knowledge_base_id,
        data_source_id=args.data_source_id,
    )
    print(
        f"Started ingestion job {job.get('ingestionJobId')} "
        f"(status={job.get('status')})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
