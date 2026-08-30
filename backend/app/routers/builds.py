"""
FastAPI router for build history and repo stats endpoints.

Endpoints:
  GET /builds                        — list recent builds for a repo
  GET /builds/{run_id}               — single build run document
  GET /repos/{repo_id}/accuracy      — accuracy trend (MAE over history_depth)
  GET /repos/{repo_id}/hotpaths      — top risky file paths
"""

from __future__ import annotations

import random

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.config import CLOUDANT_URL
from app.services.build_dna import get_db_name

router = APIRouter()


# ---------------------------------------------------------------------------
# Demo / fallback data
# ---------------------------------------------------------------------------

def _demo_accuracy_data() -> list[dict]:
    """80 data points showing MAE improving from ~0.44 down to ~0.17."""
    rng = random.Random(42)
    points: list[dict] = []
    for i in range(1, 81):
        if i <= 20:
            mae = round(rng.uniform(0.40, 0.48), 4)
        elif i <= 50:
            mae = round(rng.uniform(0.22, 0.38), 4)
        else:
            mae = round(rng.uniform(0.12, 0.22), 4)
        points.append({"history_depth": i, "mae": mae, "build_index": i})
    return points


_DEMO_HOTPATHS = [
    {"file_path": "requirements.txt", "failure_rate": 0.72, "total_runs": 18},
    {"file_path": "tests/test_main.py", "failure_rate": 0.55, "total_runs": 22},
    {"file_path": "src/main.py", "failure_rate": 0.45, "total_runs": 20},
    {"file_path": "Dockerfile", "failure_rate": 0.60, "total_runs": 15},
    {"file_path": "src/config.py", "failure_rate": 0.38, "total_runs": 12},
]

_DEMO_BUILDS = [
    {
        "run_id": "demo-run-001",
        "repo_id": "pipeline-prophet-demo",
        "commit_sha": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
        "author": "sameer",
        "branch": "main",
        "status": "failed",
        "changed_files": ["requirements.txt", "src/main.py"],
        "stage_results": {
            "install": "passed", "test": "failed", "lint": "passed", "build": "skipped"
        },
    },
    {
        "run_id": "demo-run-002",
        "repo_id": "pipeline-prophet-demo",
        "commit_sha": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1",
        "author": "sameer",
        "branch": "main",
        "status": "passed",
        "changed_files": ["README.md"],
        "stage_results": {
            "install": "passed", "test": "passed", "lint": "passed", "build": "passed"
        },
    },
    {
        "run_id": "demo-run-003",
        "repo_id": "pipeline-prophet-demo",
        "commit_sha": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2",
        "author": "sameer",
        "branch": "feature/refactor",
        "status": "failed",
        "changed_files": ["Dockerfile", "src/config.py"],
        "stage_results": {
            "install": "passed", "test": "passed", "lint": "failed", "build": "failed"
        },
    },
    {
        "run_id": "demo-run-004",
        "repo_id": "pipeline-prophet-demo",
        "commit_sha": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3",
        "author": "sameer",
        "branch": "main",
        "status": "passed",
        "changed_files": ["tests/test_main.py"],
        "stage_results": {
            "install": "passed", "test": "passed", "lint": "passed", "build": "passed"
        },
    },
    {
        "run_id": "demo-run-005",
        "repo_id": "pipeline-prophet-demo",
        "commit_sha": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4",
        "author": "sameer",
        "branch": "main",
        "status": "failed",
        "changed_files": ["requirements.txt"],
        "stage_results": {
            "install": "failed", "test": "skipped", "lint": "skipped", "build": "skipped"
        },
    },
]


# ---------------------------------------------------------------------------
# GET /builds
# ---------------------------------------------------------------------------

@router.get("/builds")
async def list_builds(repo_id: str = Query(..., description="Repository identifier")) -> list[dict]:
    """Return up to 20 most recent build runs for the given repo."""
    if not CLOUDANT_URL:
        return [b for b in _DEMO_BUILDS if b["repo_id"] == repo_id] or _DEMO_BUILDS

    from app.services.cloudant_client import query_docs
    try:
        docs = await query_docs(
            db=get_db_name("build_runs"),
            selector={"repo_id": repo_id},
            limit=20,
        )
        # Normalise: frontend reads b.status but Cloudant stores b.outcome
        for doc in docs:
            if "status" not in doc:
                doc["status"] = doc.get("outcome", "pending")
            # Normalise run_id: frontend uses b.run_id but Cloudant uses _id
            if "run_id" not in doc:
                doc["run_id"] = doc.get("_id", "")
        return docs
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /builds/{run_id}
# ---------------------------------------------------------------------------

@router.get("/builds/{run_id}")
async def get_build(run_id: str) -> dict:
    """Fetch a single build run document."""
    if not CLOUDANT_URL:
        for b in _DEMO_BUILDS:
            if b["run_id"] == run_id:
                return b
        raise HTTPException(status_code=404, detail=f"Build run '{run_id}' not found")

    from app.services.cloudant_client import get_doc
    try:
        doc = await get_doc(db=get_db_name("build_runs"), doc_id=run_id)
        return doc
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /repos/{repo_id}/accuracy
# ---------------------------------------------------------------------------

@router.get("/repos/{repo_id}/accuracy")
async def repo_accuracy(repo_id: str) -> list[dict]:
    """Return accuracy trend (MAE per history_depth) for the given repo."""
    if not CLOUDANT_URL:
        return _demo_accuracy_data()

    from app.services.cloudant_client import query_docs
    try:
        docs = await query_docs(
            db=get_db_name("predictions"),
            selector={"repo_id": repo_id},
            limit=200,
        )
    except Exception:
        return _demo_accuracy_data()

    # Only include predictions that have actual_outcomes populated
    # Also accept docs that have pre-computed mean_absolute_error (seeded docs)
    points: list[dict] = []
    for i, doc in enumerate(docs, start=1):
        hd = doc.get("history_depth_at_prediction", i)

        # Case 1: pre-computed MAE present (seeded accuracy docs)
        if "mean_absolute_error" in doc and doc["mean_absolute_error"] is not None:
            mae = round(float(doc["mean_absolute_error"]), 4)
            points.append({"history_depth": hd, "mae": mae, "build_index": i})
            continue

        # Case 2: compute from stage_predictions vs actual_outcomes
        actual = doc.get("actual_outcomes", {})
        predicted = doc.get("stage_predictions", {})
        if not actual or not predicted:
            continue
        errors = []
        for stage, act_raw in actual.items():
            if stage not in predicted:
                continue
            # stage_predictions may be {stage: {probability: float}} or {stage: float}
            pred_entry = predicted[stage]
            if isinstance(pred_entry, dict):
                pred_val = float(pred_entry.get("probability", 0.5))
            else:
                pred_val = float(pred_entry)
            # actual_outcomes may be float (1.0/0.0) or string ("failed"/"passed")
            if isinstance(act_raw, str):
                act_val = 1.0 if act_raw == "failed" else 0.0
            else:
                act_val = float(act_raw)
            errors.append(abs(pred_val - act_val))
        if errors:
            mae = round(sum(errors) / len(errors), 4)
            points.append({"history_depth": hd, "mae": mae, "build_index": i})

    if not points:
        return _demo_accuracy_data()

    return sorted(points, key=lambda x: x["history_depth"])


# ---------------------------------------------------------------------------
# GET /repos/{repo_id}/hotpaths
# ---------------------------------------------------------------------------

@router.get("/repos/{repo_id}/hotpaths")
async def repo_hotpaths(repo_id: str) -> list[dict]:
    """Return top 10 highest-risk file paths for the given repo."""
    if not CLOUDANT_URL:
        return _DEMO_HOTPATHS

    from app.services.cloudant_client import query_docs
    try:
        docs = await query_docs(
            db=get_db_name("file_stage_failures"),
            selector={"repo_id": repo_id},
            limit=500,
        )
    except Exception:
        return _DEMO_HOTPATHS

    # Aggregate by file_path (summing across stages)
    aggregated: dict[str, dict] = {}
    for doc in docs:
        fp = doc.get("file_path", "")
        if not fp:
            continue
        if fp not in aggregated:
            aggregated[fp] = {"failure_count": 0, "run_count": 0}
        aggregated[fp]["failure_count"] += doc.get("failure_count", 0)
        aggregated[fp]["run_count"] += doc.get("run_count", 0)

    if not aggregated:
        return _DEMO_HOTPATHS

    results = []
    for fp, counts in aggregated.items():
        rc = counts["run_count"]
        if rc == 0:
            continue
        results.append({
            "file_path": fp,
            "failure_rate": round(counts["failure_count"] / rc, 4),
            "total_runs": rc,
        })

    results.sort(key=lambda x: x["failure_rate"], reverse=True)
    return results[:10]


# ---------------------------------------------------------------------------
# POST /builds/{run_id}/outcome
# ---------------------------------------------------------------------------

class OutcomeUpdate(BaseModel):
    actual_outcomes: dict  # {"install": "failed", "test": "passed", ...}


@router.post("/builds/{run_id}/outcome")
async def post_outcome(run_id: str, body: OutcomeUpdate) -> dict:
    """
    Record actual pipeline outcomes for a build run and compute accuracy metrics.
    Updates the prediction document with absolute_errors and mean_absolute_error.
    """
    if not CLOUDANT_URL:
        # Demo: pull the in-memory prediction if available, otherwise use 0.5 baseline
        from app.routers.webhook import _latest_predictions
        actual = body.actual_outcomes
        errors: dict[str, float] = {}

        # Try to find a recent prediction for any repo that matches this run_id
        stage_preds_raw: dict = {}
        for pred_result in _latest_predictions.values():
            if pred_result.run_id == run_id or run_id in ("local-fallback", "unknown"):
                stage_preds_raw = {
                    stage: {"probability": sp.probability, "risk": (
                        "high" if sp.probability >= 0.6 else
                        "medium" if sp.probability >= 0.3 else "low"
                    )}
                    for stage, sp in pred_result.stage_predictions.items()
                }
                break

        # Fallback to 0.5 if no match
        if not stage_preds_raw:
            stage_preds_raw = {stage: {"probability": 0.5, "risk": "medium"} for stage in actual}

        for stage, outcome_str in actual.items():
            actual_float = 1.0 if outcome_str == "failed" else 0.0
            prob = stage_preds_raw.get(stage, {}).get("probability", 0.5)
            errors[stage] = round(abs(prob - actual_float), 4)
        mae = round(sum(errors.values()) / len(errors), 4) if errors else 0.0
        return {
            "run_id": run_id,
            "demo_mode": True,
            "stage_predictions": stage_preds_raw,
            "actual_outcomes": actual,
            "absolute_errors": errors,
            "mean_absolute_error": mae,
        }

    from app.services.build_dna import update_prediction_outcome
    import asyncio
    try:
        result = await asyncio.to_thread(
            update_prediction_outcome, run_id, body.actual_outcomes
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /repos/{repo_id}/stats
# ---------------------------------------------------------------------------

_DEMO_STATS = {
    "repo_id": "pipeline-prophet-demo",
    "total_builds": 80,
    "total_predictions": 80,
    "current_mae": 0.17,
    "improvement_pct": 62,
    "most_risky_stage": "test",
    "most_risky_file": "requirements.txt",
}


@router.get("/repos/{repo_id}/stats")
async def repo_stats(repo_id: str) -> dict:
    """
    Return summary stats for the dashboard header.
    current_mae = rolling average of latest 10 builds.
    improvement_pct = reduction from first-10 avg MAE to last-10 avg MAE.
    """
    if not CLOUDANT_URL:
        return {**_DEMO_STATS, "repo_id": repo_id}

    from app.services.cloudant_client import query_docs
    try:
        pred_docs = await query_docs(
            db=get_db_name("predictions"),
            selector={"repo_id": repo_id},
            limit=500,
        )
        build_docs = await query_docs(
            db=get_db_name("build_runs"),
            selector={"repo_id": repo_id},
            limit=500,
        )
    except Exception:
        return {**_DEMO_STATS, "repo_id": repo_id}

    total_builds = len(build_docs)
    total_predictions = len(pred_docs)

    # Collect MAE series from predictions that have been scored
    mae_series: list[float] = []
    for doc in pred_docs:
        mae = doc.get("mean_absolute_error")
        if mae is not None:
            mae_series.append(float(mae))

    if not mae_series:
        return {**_DEMO_STATS, "repo_id": repo_id,
                "total_builds": total_builds, "total_predictions": total_predictions}

    current_mae = round(sum(mae_series[-10:]) / len(mae_series[-10:]), 4)

    first10 = mae_series[:10]
    last10 = mae_series[-10:]
    first_avg = sum(first10) / len(first10) if first10 else 0
    last_avg = sum(last10) / len(last10) if last10 else 0
    improvement_pct = (
        round((first_avg - last_avg) / first_avg * 100) if first_avg > 0 else 0
    )

    # Most risky stage and file from file_stage_failures
    stage_failure_totals: dict[str, dict[str, int]] = {}
    file_failure_totals: dict[str, dict[str, int]] = {}
    try:
        fsf_docs = await query_docs(
            db=get_db_name("file_stage_failures"),
            selector={"repo_id": repo_id},
            limit=1000,
        )
        for doc in fsf_docs:
            stage = doc.get("stage_name", "")
            if stage:
                if stage not in stage_failure_totals:
                    stage_failure_totals[stage] = {"fc": 0, "rc": 0}
                stage_failure_totals[stage]["fc"] += doc.get("failure_count", 0)
                stage_failure_totals[stage]["rc"] += doc.get("run_count", 0)
            fp = doc.get("file_path", "")
            if fp:
                if fp not in file_failure_totals:
                    file_failure_totals[fp] = {"fc": 0, "rc": 0}
                file_failure_totals[fp]["fc"] += doc.get("failure_count", 0)
                file_failure_totals[fp]["rc"] += doc.get("run_count", 0)
    except Exception:
        pass

    most_risky_stage = "test"
    best_rate = -1.0
    for stage, counts in stage_failure_totals.items():
        rc = counts["rc"]
        if rc > 0:
            rate = counts["fc"] / rc
            if rate > best_rate:
                best_rate = rate
                most_risky_stage = stage

    most_risky_file = "requirements.txt"
    best_file_rate = -1.0
    for fp, counts in file_failure_totals.items():
        rc = counts["rc"]
        if rc > 0:
            rate = counts["fc"] / rc
            if rate > best_file_rate:
                best_file_rate = rate
                most_risky_file = fp

    return {
        "repo_id": repo_id,
        "total_builds": total_builds,
        "total_predictions": total_predictions,
        "current_mae": current_mae,
        "improvement_pct": improvement_pct,
        "most_risky_stage": most_risky_stage,
        "most_risky_file": most_risky_file,
    }
