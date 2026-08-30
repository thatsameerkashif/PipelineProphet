"""
FastAPI router for GitHub webhook events.

Endpoints:
  POST /webhook                             — receive GitHub push events
  GET  /repos/{repo_id}/latest-prediction   — poll for latest prediction result
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.config import GITHUB_WEBHOOK_SECRET
from app.services import prediction_engine
from app.services.prediction_engine import PredictionResult

router = APIRouter()

# Module-level store: repo_id -> latest PredictionResult
_latest_predictions: dict[str, PredictionResult] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_signature(body: bytes, signature_header: str | None) -> bool:
    """Return True if signature matches or secret is not configured (demo mode)."""
    if not GITHUB_WEBHOOK_SECRET:
        return True  # demo mode — skip validation
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _collect_changed_files(commits: list[dict]) -> list[str]:
    """Return a deduplicated list of all changed file paths across all commits."""
    seen: set[str] = set()
    result: list[str] = []
    for commit in commits:
        for path in commit.get("added", []) + commit.get("modified", []) + commit.get("removed", []):
            if path not in seen:
                seen.add(path)
                result.append(path)
    return result


def _run_prediction(
    repo_id: str,
    commit_sha: str,
    author: str,
    branch: str,
    changed_files: list[str],
) -> None:
    """Background task: run prediction and store result."""
    result: PredictionResult = prediction_engine.predict(
        repo_id, commit_sha, author, branch, changed_files
    )
    _latest_predictions[repo_id] = result


# ---------------------------------------------------------------------------
# POST /webhook
# ---------------------------------------------------------------------------

@router.post("/webhook", status_code=202)
async def github_webhook(request: Request, background_tasks: BackgroundTasks) -> dict:
    body = await request.body()

    # 1. Validate signature
    sig_header = request.headers.get("X-Hub-Signature-256")
    if not _verify_signature(body, sig_header):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # 2. Only handle push events
    event_type = request.headers.get("X-GitHub-Event", "unknown")
    if event_type != "push":
        return {"status": "ignored", "event": event_type}

    # 3. Extract fields from payload
    import json as _json
    payload: dict = _json.loads(body)

    commit_sha: str = payload["after"]
    author: str = payload["pusher"]["name"]
    branch: str = payload["ref"].split("/")[-1]
    repo_id: str = payload["repository"]["name"]
    changed_files: list[str] = _collect_changed_files(payload.get("commits", []))

    # 4. Return 202 immediately; run prediction in background
    background_tasks.add_task(
        asyncio.to_thread,
        _run_prediction,
        repo_id,
        commit_sha,
        author,
        branch,
        changed_files,
    )

    return {"status": "accepted", "commit_sha": commit_sha}


# ---------------------------------------------------------------------------
# GET /repos/{repo_id}/latest-prediction
# ---------------------------------------------------------------------------

@router.get("/repos/{repo_id}/latest-prediction")
async def latest_prediction(repo_id: str) -> dict:
    """Return the most recent prediction for a repo (polled by the frontend)."""
    result = _latest_predictions.get(repo_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No prediction available yet for repo '{repo_id}'",
        )
    return {
        "run_id": result.run_id,
        "commit_sha": result.commit_sha,
        "repo_id": result.repo_id,
        "changed_files": result.changed_files,
        "stage_predictions": {
            stage: {
                "probability": sp.probability,
                "rationale": sp.rationale,
            }
            for stage, sp in result.stage_predictions.items()
        },
        "overall_risk": result.overall_risk,
        "summary": result.summary,
        "history_depth": result.history_depth,
        "prediction_doc_id": result.prediction_doc_id,
    }
