#!/usr/bin/env python3
"""
Seed 80 synthetic build records into Cloudant for the pipeline-prophet-demo repo.

Run from the project root (after create_databases.py):
    python backend/scripts/seed_build_history.py

Set random.seed(42) for full reproducibility.
"""

import sys
import os
import random
import string
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import CLOUDANT_URL
from app.services.cloudant_client import client
from app.services.build_dna import (
    get_db_name,
    upsert_file_stage_failure,
    save_prediction,
)
from ibmcloudant.cloudant_v1 import Document

random.seed(42)

# ---------------------------------------------------------------------------
# Demo configuration
# ---------------------------------------------------------------------------

REPO_ID = "pipeline-prophet-demo"
STAGES = ["install", "test", "lint", "build"]
AUTHORS = ["sameer", "alice", "bob"]
BRANCHES = ["main", "feature/auth", "fix/bug-123"]

# File → stage → base failure rate
FILE_FAILURE_RATES: dict[str, dict[str, float]] = {
    "requirements.txt": {"install": 0.72, "test": 0.35},
    "src/main.py":      {"lint":    0.45, "test": 0.28},
    "tests/test_main.py": {"test":  0.55, "lint": 0.20},
    "src/config.py":    {"install": 0.15, "test": 0.38},
    "Dockerfile":       {"build":   0.60, "install": 0.25},
}
ALL_FILES = list(FILE_FAILURE_RATES.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_sha() -> str:
    return "".join(random.choices(string.hexdigits[:16], k=40))


def _stage_failed(file_path: str, stage: str) -> bool:
    """Probabilistic outcome with ±10 % noise."""
    base = FILE_FAILURE_RATES.get(file_path, {}).get(stage, 0.05)
    noise = random.uniform(-0.10, 0.10)
    return random.random() < max(0.0, min(1.0, base + noise))


def _insert_doc(db: str, doc: dict) -> None:
    client.post_document(db=db, document=Document.from_dict(doc))


# ---------------------------------------------------------------------------
# Prediction MAE targets per era
# ---------------------------------------------------------------------------

def _mae_target(build_index: int) -> tuple[float, float]:
    """Return (lo, hi) MAE target range for this build index (1-based)."""
    if build_index <= 20:
        return (0.40, 0.45)
    if build_index <= 50:
        return (0.25, 0.35)
    return (0.12, 0.22)


def _synthetic_prediction_pair(
    build_index: int,
    actual: dict[str, float],
) -> tuple[dict, dict]:
    """
    Returns (stage_predictions, absolute_errors) such that mean(absolute_errors)
    falls within the MAE target for this era.
    """
    lo, hi = _mae_target(build_index)
    target_mae = random.uniform(lo, hi)

    preds: dict[str, dict] = {}
    errors: dict[str, float] = {}

    for stage in STAGES:
        act = actual[stage]
        # Generate a prediction that, on average across stages, hits target_mae.
        # Simple approach: add a signed offset drawn from N(target_mae, 0.05).
        error = abs(random.gauss(target_mae, 0.05))
        error = min(error, 1.0)
        # Randomly flip sign so predictions aren't always biased in one direction.
        pred_val = act + (error if random.random() < 0.5 else -error)
        pred_val = max(0.0, min(1.0, pred_val))
        preds[stage] = {
            "probability": round(pred_val, 3),
            "rationale": f"Synthetic seed prediction (era {build_index})",
        }
        errors[stage] = round(abs(pred_val - act), 3)

    return preds, errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not CLOUDANT_URL:
        print("ERROR: CLOUDANT_URL is not set. Configure your .env and retry.")
        sys.exit(1)

    if client is None:
        print("ERROR: Cloudant client could not be initialised (missing credentials).")
        sys.exit(1)

    db_runs = get_db_name("build_runs")
    db_outcomes = get_db_name("stage_outcomes")
    db_predictions = get_db_name("predictions")

    base_time = datetime.now(timezone.utc) - timedelta(days=80)

    print(f"\nSeeding 80 build records for repo '{REPO_ID}' …\n")

    for i in range(1, 81):
        # --- Build run metadata ---
        run_id = f"seed-run-{i:03d}"
        commit_sha = _random_sha()
        author = random.choice(AUTHORS)
        branch = random.choice(BRANCHES)
        num_files = random.randint(1, 3)
        changed_files = random.sample(ALL_FILES, num_files)
        started_at = (base_time + timedelta(days=i)).isoformat() + "Z"

        # --- Determine stage outcomes ---
        # A stage fails if ANY changed file triggers a failure in that stage.
        stage_outcomes: dict[str, bool] = {}
        for stage in STAGES:
            failed = any(_stage_failed(f, stage) for f in changed_files)
            stage_outcomes[stage] = failed

        # Convert to float probabilities (1.0 = failed, 0.0 = passed)
        actual_probs: dict[str, float] = {s: 1.0 if v else 0.0 for s, v in stage_outcomes.items()}

        # --- Insert build_run document ---
        run_doc = {
            "_id": run_id,
            "repo_id": REPO_ID,
            "commit_sha": commit_sha,
            "author": author,
            "branch": branch,
            "changed_files": changed_files,
            "outcome": "failed" if any(stage_outcomes.values()) else "passed",
            "started_at": started_at,
        }
        _insert_doc(db_runs, run_doc)

        # --- Insert stage_outcome documents ---
        for stage, failed in stage_outcomes.items():
            outcome_doc = {
                "_id": f"{run_id}:{stage}",
                "run_id": run_id,
                "repo_id": REPO_ID,
                "stage_name": stage,
                "outcome": "failed" if failed else "passed",
                "recorded_at": started_at,
            }
            _insert_doc(db_outcomes, outcome_doc)

        # --- Update file_stage_failure aggregates ---
        for file_path in changed_files:
            for stage in STAGES:
                failed = stage_outcomes[stage]
                upsert_file_stage_failure(REPO_ID, file_path, stage, failed)

        # --- Insert prediction document ---
        stage_preds, abs_errors = _synthetic_prediction_pair(i, actual_probs)
        pred_doc = {
            "_id": f"seed-pred-{i:03d}",
            "run_id": run_id,
            "repo_id": REPO_ID,
            "stage_predictions": stage_preds,
            "actual_outcomes": actual_probs,
            "absolute_errors": abs_errors,
            "history_depth_at_prediction": i - 1,  # depth before this build
            "created_at": started_at,
        }
        _insert_doc(db_predictions, pred_doc)

        # --- Progress ---
        if i % 10 == 0:
            failed_stages = [s for s, v in stage_outcomes.items() if v]
            print(
                f"  [{i:3d}/80]  run={run_id}  files={len(changed_files)}"
                f"  failed_stages={failed_stages or 'none'}"
            )

    print("\nSeed complete. 80 builds, 80 predictions inserted.\n")


if __name__ == "__main__":
    main()
