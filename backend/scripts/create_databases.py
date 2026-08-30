#!/usr/bin/env python3
"""
Create the four Pipeline Prophet Cloudant databases and their Mango indexes.

Run from the project root:
    python backend/scripts/create_databases.py

Databases created (all idempotent — 412 "already exists" is treated as success):
  - pp_build_runs
  - pp_stage_outcomes
  - pp_file_stage_failures
  - pp_predictions
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import CLOUDANT_URL
from app.services.cloudant_client import client
from app.services.build_dna import get_db_name
from ibm_cloud_sdk_core import ApiException


def put_db(db_name: str) -> None:
    """Create database; ignore 412 (already exists)."""
    try:
        client.put_database(db=db_name).get_result()
        print(f"  CREATED  {db_name}")
    except ApiException as exc:
        if exc.code == 412:
            print(f"  EXISTS   {db_name}")
        else:
            raise


def create_index(db_name: str, fields: list[str]) -> None:
    """Create a Mango index on *fields* for *db_name*."""
    index_name = "_".join(fields) + "_idx"
    try:
        client.post_index(
            db=db_name,
            index={"fields": fields},
            name=index_name,
            type="json",
        ).get_result()
        print(f"  INDEX    {db_name}  [{', '.join(fields)}]")
    except ApiException as exc:
        print(f"  WARN     index on {db_name} [{', '.join(fields)}]: {exc}")


def main() -> None:
    if not CLOUDANT_URL:
        print("ERROR: CLOUDANT_URL is not set. Configure your .env and retry.")
        sys.exit(1)

    if client is None:
        print("ERROR: Cloudant client could not be initialised (missing credentials).")
        sys.exit(1)

    print("\n-- Creating databases --------------------------------")
    databases = [
        "build_runs",
        "stage_outcomes",
        "file_stage_failures",
        "predictions",
    ]
    for suffix in databases:
        put_db(get_db_name(suffix))

    print("\n-- Creating Mango indexes ----------------------------")
    create_index(get_db_name("build_runs"), ["repo_id"])
    create_index(get_db_name("file_stage_failures"), ["repo_id", "file_path"])
    create_index(get_db_name("predictions"), ["repo_id", "history_depth_at_prediction"])

    print("\nDone.\n")


if __name__ == "__main__":
    main()
