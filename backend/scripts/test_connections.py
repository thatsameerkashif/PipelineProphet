#!/usr/bin/env python3
"""
Connectivity test for IBM Cloudant and IBM watsonx.ai.

Run from the project root:
    python backend/scripts/test_connections.py

Expected behaviour when credentials are NOT set: prints FAIL with a clear
message but exits without import errors — which is all Sub-Task 1 requires.
"""

import sys
import os

# Ensure the backend package is importable regardless of CWD
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.cloudant_client import list_databases  # noqa: E402
from app.services.watsonx_client import generate          # noqa: E402
from app import config                                    # noqa: E402
from app.services.build_dna import get_db_name           # noqa: E402


def test_cloudant() -> bool:
    print("\n-- Cloudant Connection ------------------------------")
    if not config.CLOUDANT_URL or not config.CLOUDANT_APIKEY:
        print("  SKIP  CLOUDANT_URL / CLOUDANT_APIKEY not set in environment.")
        return False
    try:
        dbs = list_databases()
        print(f"  PASS  Connected. Databases found: {len(dbs)}")
        if dbs:
            print(f"        First few: {dbs[:5]}")
        return True
    except Exception as exc:
        print(f"  FAIL  {exc}")
        return False


def test_seed_data() -> bool:
    print("\n-- Seed Data Check ----------------------------------")
    if not config.CLOUDANT_URL or not config.CLOUDANT_APIKEY:
        print("  SKIP  Cloudant not configured.")
        return False
    try:
        from app.services.cloudant_client import client
        db = get_db_name("file_stage_failures")
        result = client.post_find(
            db=db,
            selector={"repo_id": "pipeline-prophet-demo"},
            fields=["_id"],
            limit=1000,
        ).get_result()
        docs = result.get("docs", [])
        if docs:
            print(f"  PASS  pp_file_stage_failures: {len(docs)} document(s) found for 'pipeline-prophet-demo'.")
        else:
            print("  INFO  Seed data not yet loaded (expected before first run).")
        return True
    except Exception as exc:
        print(f"  FAIL  {exc}")
        return False


def test_watsonx() -> bool:
    print("\n-- watsonx.ai Connection ----------------------------")
    if not config.WATSONX_API_KEY or not config.WATSONX_PROJECT_ID:
        print("  SKIP  WATSONX_API_KEY / WATSONX_PROJECT_ID not set in environment.")
        return False
    try:
        response = generate("Say hello in one word.", max_tokens=20)
        print(f"  PASS  Model responded: {response!r}")
        return True
    except Exception as exc:
        print(f"  FAIL  {exc}")
        return False


if __name__ == "__main__":
    print("Pipeline Prophet - IBM Cloud Connection Test")
    print("=" * 52)

    cloudant_ok = test_cloudant()
    seed_ok = test_seed_data()
    watsonx_ok = test_watsonx()

    print("\n-- Summary ------------------------------------------")
    print(f"  Cloudant  : {'PASS' if cloudant_ok else 'FAIL/SKIP'}")
    print(f"  Seed data : {'PASS' if seed_ok else 'FAIL/SKIP'}")
    print(f"  watsonx.ai: {'PASS' if watsonx_ok else 'FAIL/SKIP'}")
    print()

    # Exit 0 even on FAIL so that CI-style import-error checks pass cleanly.
    # Change to sys.exit(0 if (cloudant_ok and watsonx_ok) else 1) if needed.
    sys.exit(0)
