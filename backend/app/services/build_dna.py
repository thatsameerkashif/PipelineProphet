"""
Build DNA data-access module.

All functions that touch Cloudant are synchronous (used directly by scripts
and also called from async FastAPI routes via asyncio.to_thread).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from uuid import uuid4

try:
    from ibmcloudant.cloudant_v1 import Document
    from ibm_cloud_sdk_core import ApiException
    _IBM_CLOUDANT_AVAILABLE = True
except ImportError:
    Document = None   # type: ignore[assignment,misc]
    ApiException = Exception  # type: ignore[assignment,misc]
    _IBM_CLOUDANT_AVAILABLE = False

from app.config import CLOUDANT_URL, CLOUDANT_DB_PREFIX
from app.services.cloudant_client import client as _client

# ---------------------------------------------------------------------------
# Pipeline stage catalogue
# ---------------------------------------------------------------------------

PIPELINE_STAGES: list[str] = ["install", "test", "lint", "build"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_client():
    """Raises RuntimeError if Cloudant is not configured."""
    if not CLOUDANT_URL:
        raise RuntimeError("Cloudant not configured")
    return _client


def get_db_name(suffix: str) -> str:
    """Returns CLOUDANT_DB_PREFIX + suffix, e.g. 'pp_build_runs'."""
    return f"{CLOUDANT_DB_PREFIX}{suffix}"


# ---------------------------------------------------------------------------
# file_stage_failures — aggregate co-occurrence table
# ---------------------------------------------------------------------------

def upsert_file_stage_failure(
    repo_id: str, file_path: str, stage_name: str, failed: bool
) -> None:
    """
    Increments run_count (always) and failure_count (if failed=True)
    for the document with _id = f"{repo_id}:{file_path}:{stage_name}".
    Creates the document if it doesn't exist.
    """
    cl = _require_client()
    db = get_db_name("file_stage_failures")
    doc_id = f"{repo_id}:{file_path}:{stage_name}"

    try:
        existing = cl.get_document(db=db, doc_id=doc_id).get_result()
        rev = existing["_rev"]
        run_count = existing.get("run_count", 0) + 1
        failure_count = existing.get("failure_count", 0) + (1 if failed else 0)
        doc = {
            "_id": doc_id,
            "_rev": rev,
            "repo_id": repo_id,
            "file_path": file_path,
            "stage_name": stage_name,
            "failure_count": failure_count,
            "run_count": run_count,
        }
    except ApiException as exc:
        if exc.code != 404:
            raise
        doc = {
            "_id": doc_id,
            "repo_id": repo_id,
            "file_path": file_path,
            "stage_name": stage_name,
            "failure_count": 1 if failed else 0,
            "run_count": 1,
        }

    cl.post_document(db=db, document=Document.from_dict(doc))


# ---------------------------------------------------------------------------
# Demo fallback data (used when Cloudant is not configured)
# ---------------------------------------------------------------------------

_DEMO_FILE_STAGE_RATES: dict[str, dict[str, float]] = {
    # file_path -> {stage -> failure_rate}
    "requirements.txt": {"install": 0.72, "test": 0.20, "lint": 0.10, "build": 0.15},
    "tests/test_main.py": {"install": 0.10, "test": 0.55, "lint": 0.15, "build": 0.10},
    "src/main.py":        {"install": 0.15, "test": 0.45, "lint": 0.38, "build": 0.20},
    "Dockerfile":         {"install": 0.20, "test": 0.10, "lint": 0.15, "build": 0.60},
    "src/config.py":      {"install": 0.10, "test": 0.25, "lint": 0.38, "build": 0.15},
}

_DEMO_DEFAULT_RATES: dict[str, float] = {
    "install": 0.12, "test": 0.18, "lint": 0.10, "build": 0.08
}


def demo_query_failure_rates(changed_files: list[str]) -> dict[str, float]:
    """Statistical fallback used when Cloudant is not configured."""
    totals: dict[str, dict[str, float]] = {
        s: {"sum": 0.0, "count": 0} for s in PIPELINE_STAGES
    }
    for file_path in changed_files:
        rates = _DEMO_FILE_STAGE_RATES.get(file_path, _DEMO_DEFAULT_RATES)
        for stage, rate in rates.items():
            totals[stage]["sum"] += rate
            totals[stage]["count"] += 1
    result: dict[str, float] = {}
    for stage, t in totals.items():
        if t["count"] > 0:
            result[stage] = round(t["sum"] / t["count"], 4)
        else:
            result[stage] = _DEMO_DEFAULT_RATES.get(stage, 0.1)
    return result


def query_failure_rates(repo_id: str, changed_files: list[str]) -> dict:
    """
    Returns {stage_name: failure_rate_float} aggregated across all changed_files.
    If no history at all, returns {stage: 0.0} for all stages.
    Falls back to demo data when Cloudant is not configured.
    """
    if not CLOUDANT_URL:
        return demo_query_failure_rates(changed_files)
    cl = _require_client()
    db = get_db_name("file_stage_failures")

    totals: dict[str, dict[str, int]] = {
        s: {"failure_count": 0, "run_count": 0} for s in PIPELINE_STAGES
    }

    for file_path in changed_files:
        for stage in PIPELINE_STAGES:
            doc_id = f"{repo_id}:{file_path}:{stage}"
            try:
                doc = cl.get_document(db=db, doc_id=doc_id).get_result()
                totals[stage]["failure_count"] += doc.get("failure_count", 0)
                totals[stage]["run_count"] += doc.get("run_count", 0)
            except ApiException as exc:
                if exc.code != 404:
                    raise
                # no history for this combo — contributes 0/0

    result: dict[str, float] = {}
    for stage, counts in totals.items():
        rc = counts["run_count"]
        result[stage] = counts["failure_count"] / rc if rc > 0 else 0.0

    return result


# ---------------------------------------------------------------------------
# build_runs
# ---------------------------------------------------------------------------

def create_build_run(
    repo_id: str,
    commit_sha: str,
    author: str,
    branch: str,
    changed_files: list[str],
) -> str:
    """Creates a build_run document and returns its _id."""
    from datetime import timezone
    cl = _require_client()
    db = get_db_name("build_runs")
    run_id = str(uuid4())
    doc = {
        "_id": run_id,
        "repo_id": repo_id,
        "commit_sha": commit_sha,
        "author": author,
        "branch": branch,
        "changed_files": changed_files,
        "outcome": "predicted",
        "status": "predicted",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    cl.post_document(db=db, document=Document.from_dict(doc))
    return run_id


def update_build_run_status(run_id: str, status: str, prediction_id: str = "") -> None:
    """Updates the status/outcome of a build_run document."""
    cl = _require_client()
    db = get_db_name("build_runs")
    try:
        existing = cl.get_document(db=db, doc_id=run_id).get_result()
        existing["outcome"] = status
        existing["status"] = status
        if prediction_id:
            existing["prediction_id"] = prediction_id
        cl.post_document(db=db, document=Document.from_dict(existing))
    except Exception:
        pass  # best-effort update


def get_build_run_count(repo_id: str) -> int:
    """Returns count of build_run documents for a repo_id. Returns 80 in demo mode."""
    if not CLOUDANT_URL:
        return 80  # demo mode — matches seeded data count
    cl = _require_client()
    db = get_db_name("build_runs")
    result = cl.post_find(
        db=db,
        selector={"repo_id": repo_id},
        fields=["_id"],
        limit=1000,
    ).get_result()
    return len(result.get("docs", []))


# ---------------------------------------------------------------------------
# predictions
# ---------------------------------------------------------------------------

def save_prediction(
    run_id: str,
    repo_id: str,
    stage_predictions: dict,
    history_depth: int,
) -> str:
    """Creates a prediction document and returns its _id."""
    cl = _require_client()
    db = get_db_name("predictions")
    pred_id = str(uuid4())
    doc = {
        "_id": pred_id,
        "run_id": run_id,
        "repo_id": repo_id,
        "stage_predictions": stage_predictions,
        "actual_outcomes": {},
        "absolute_errors": {},
        "history_depth_at_prediction": history_depth,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    cl.post_document(db=db, document=Document.from_dict(doc))
    return pred_id


# ---------------------------------------------------------------------------
# update_prediction_outcome
# ---------------------------------------------------------------------------

def update_prediction_outcome(run_id: str, actual_outcomes: dict) -> dict:
    """
    Finds the prediction document for run_id, computes per-stage absolute errors
    against the stored stage_predictions, updates the document with actual_outcomes,
    absolute_errors, and mean_absolute_error, then returns the updated document.

    Outcome strings: "failed" → 1.0, anything else → 0.0
    """
    cl = _require_client()
    db = get_db_name("predictions")

    # Find the prediction document for this run_id
    result = cl.post_find(
        db=db,
        selector={"run_id": run_id},
        limit=1,
    ).get_result()

    docs = result.get("docs", [])
    if not docs:
        raise ValueError(f"No prediction found for run_id={run_id!r}")

    pred_doc = docs[0]
    stage_predictions = pred_doc.get("stage_predictions", {})

    # Compute absolute errors
    absolute_errors: dict[str, float] = {}
    for stage, outcome_str in actual_outcomes.items():
        actual_float = 1.0 if outcome_str == "failed" else 0.0
        pred_info = stage_predictions.get(stage, {})
        pred_prob = float(pred_info.get("probability", 0.0))
        absolute_errors[stage] = round(abs(pred_prob - actual_float), 4)

    mae = round(sum(absolute_errors.values()) / len(absolute_errors), 4) if absolute_errors else 0.0

    # Update in Cloudant
    updated_doc = dict(pred_doc)
    updated_doc["actual_outcomes"] = actual_outcomes
    updated_doc["absolute_errors"] = absolute_errors
    updated_doc["mean_absolute_error"] = mae

    cl.post_document(db=db, document=Document.from_dict(updated_doc))

    return {
        "run_id": run_id,
        "stage_predictions": stage_predictions,
        "actual_outcomes": actual_outcomes,
        "absolute_errors": absolute_errors,
        "mean_absolute_error": mae,
    }
