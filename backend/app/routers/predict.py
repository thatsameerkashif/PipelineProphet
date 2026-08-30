"""
FastAPI router for pre-run predictions.

Endpoints:
  POST /predict                          — run a new prediction
  GET  /predictions/{prediction_doc_id}  — fetch a stored prediction document
  GET  /builds/{run_id}/prediction       — fetch the prediction for a build run
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import prediction_engine
from app.services.prediction_engine import PredictionResult, StagePrediction
from app.services.build_dna import get_db_name
from app.config import CLOUDANT_URL

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class PredictRequest(BaseModel):
    repo_id: str
    commit_sha: str
    author: str = "unknown"
    branch: str = "main"
    changed_files: list[str]


# ---------------------------------------------------------------------------
# POST /predict
# ---------------------------------------------------------------------------

@router.post("/predict")
async def run_prediction(req: PredictRequest) -> dict:
    """
    Trigger a pre-run prediction for the given commit.
    Returns a JSON-serialisable dict derived from PredictionResult.
    """
    result: PredictionResult = await asyncio.to_thread(
        prediction_engine.predict,
        req.repo_id,
        req.commit_sha,
        req.author,
        req.branch,
        req.changed_files,
    )

    # Serialise dataclasses to plain dicts
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


# ---------------------------------------------------------------------------
# GET /predictions/{prediction_doc_id}
# ---------------------------------------------------------------------------

@router.get("/predictions/{prediction_doc_id}")
async def get_prediction(prediction_doc_id: str) -> dict:
    """Fetch a stored prediction document from Cloudant pp_predictions."""
    if not CLOUDANT_URL:
        raise HTTPException(status_code=503, detail="Cloudant not configured")

    from app.services.cloudant_client import get_doc
    try:
        doc = await get_doc(db=get_db_name("predictions"), doc_id=prediction_doc_id)
        return doc
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /builds/{run_id}/prediction
# ---------------------------------------------------------------------------

@router.get("/builds/{run_id}/prediction")
async def get_prediction_for_build(run_id: str) -> dict:
    """Fetch the prediction document associated with a build run."""
    if not CLOUDANT_URL:
        raise HTTPException(status_code=503, detail="Cloudant not configured")

    from app.services.cloudant_client import query_docs
    try:
        docs = await query_docs(
            db=get_db_name("predictions"),
            selector={"run_id": run_id},
            limit=1,
        )
        if not docs:
            raise HTTPException(
                status_code=404,
                detail=f"No prediction found for run_id={run_id}",
            )
        return docs[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
