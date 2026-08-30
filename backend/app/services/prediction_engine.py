"""
Pre-Run Prediction Engine.

Combines Build DNA historical failure rates with IBM watsonx.ai Granite
to produce per-stage failure probability predictions before a pipeline runs.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.config import WATSONX_API_KEY
from app.services import build_dna


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class StagePrediction:
    probability: float   # 0.0 to 1.0
    rationale: str       # one sentence referencing files and history


@dataclass
class PredictionResult:
    run_id: str
    commit_sha: str
    repo_id: str
    changed_files: list
    stage_predictions: dict          # {stage_name: StagePrediction}
    overall_risk: str                # "HIGH", "MEDIUM", "LOW"
    summary: str                     # two-sentence plain-English explanation
    history_depth: int               # number of prior builds used
    prediction_doc_id: str           # Cloudant _id of stored prediction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_evidence_lines(
    changed_files: list[str],
    failure_rates: dict[str, float],
    history_depth: int,
    repo_id: str,
) -> str:
    """
    Build the evidence block for the Granite prompt.
    Fetches per-file, per-stage data directly from Build DNA when possible;
    falls back to the aggregate failure_rates dict for rationale.
    """
    lines: list[str] = []
    for file_path in changed_files:
        has_any_history = False
        for stage in build_dna.PIPELINE_STAGES:
            # Try to get individual file+stage run counts from Build DNA
            try:
                from app.services.cloudant_client import client as _cl
                from app.services.build_dna import get_db_name
                from ibm_cloud_sdk_core import ApiException

                if _cl is not None:
                    doc_id = f"{repo_id}:{file_path}:{stage}"
                    doc = _cl.get_document(
                        db=get_db_name("file_stage_failures"), doc_id=doc_id
                    ).get_result()
                    rc = doc.get("run_count", 0)
                    fc = doc.get("failure_count", 0)
                    if rc > 0:
                        rate = fc / rc
                        lines.append(
                            f"- {file_path} → {stage} stage: "
                            f"failed {rate * 100:.0f}% of {rc} runs"
                        )
                        has_any_history = True
            except Exception:
                pass  # Cloudant not available or doc missing

        if not has_any_history:
            lines.append(f"- {file_path}: no prior failure history in this repository")

    return "\n".join(lines) if lines else "- no historical data available"


def _compute_overall_risk(stage_predictions: dict[str, StagePrediction]) -> str:
    probs = [sp.probability for sp in stage_predictions.values()]
    if not probs:
        return "LOW"
    max_prob = max(probs)
    if max_prob > 0.60:
        return "HIGH"
    if max_prob > 0.35:
        return "MEDIUM"
    return "LOW"


def _statistical_prediction(
    failure_rates: dict[str, float], rationale_suffix: str
) -> dict[str, StagePrediction]:
    """Build stage predictions from raw historical rates, no LLM."""
    return {
        stage: StagePrediction(
            probability=round(rate, 4),
            rationale=f"Historical failure rate for this stage is "
                      f"{rate * 100:.1f}%. {rationale_suffix}",
        )
        for stage, rate in failure_rates.items()
    }


# ---------------------------------------------------------------------------
# Main predict function
# ---------------------------------------------------------------------------

def predict(
    repo_id: str,
    commit_sha: str,
    author: str,
    branch: str,
    changed_files: list[str],
) -> PredictionResult:
    """
    Predict per-stage failure probabilities for the given commit.
    Falls back gracefully when Cloudant or watsonx.ai is not configured.
    """

    # Step 1: history depth
    try:
        history_depth = build_dna.get_build_run_count(repo_id)
    except RuntimeError:
        history_depth = 0

    # Step 2: per-stage historical failure rates
    try:
        failure_rates: dict[str, float] = build_dna.query_failure_rates(
            repo_id, changed_files
        )
    except RuntimeError:
        failure_rates = {s: 0.5 for s in build_dna.PIPELINE_STAGES}

    # Step 3 / Step 4: build prompt and call Granite (skip if no API key)
    llm_stage_predictions: dict[str, StagePrediction] | None = None
    llm_overall_risk: str | None = None
    llm_summary: str | None = None

    if WATSONX_API_KEY:
        changed_files_formatted = ", ".join(changed_files)
        evidence_lines = _build_evidence_lines(
            changed_files, failure_rates, history_depth, repo_id
        )

        json_template = (
            '{"stage_predictions":{"install":{"probability":0.0,"rationale":"string"},'
            '"test":{"probability":0.0,"rationale":"string"},'
            '"lint":{"probability":0.0,"rationale":"string"},'
            '"build":{"probability":0.0,"rationale":"string"}},'
            '"overall_risk":"HIGH","summary":"string"}'
        )
        prompt = (
            f"You are a CI/CD failure prediction system for a software repository.\n"
            f"You have access to this repository's own build history data.\n\n"
            f"Repository: {repo_id}\n"
            f"Commit SHA: {commit_sha}\n"
            f"Author: {author}\n"
            f"Branch: {branch}\n"
            f"Changed files: {changed_files_formatted}\n\n"
            f"Historical failure evidence from {history_depth} prior builds of this repository:\n"
            f"{evidence_lines}\n\n"
            f"Based ONLY on the historical evidence above, predict the failure probability "
            f"for each pipeline stage.\n"
            f"Pipeline stages: install, test, lint, build\n\n"
            f"Rules:\n"
            f"- Use the historical rates as your primary signal\n"
            f"- If history_depth is 0, use 0.5 for all stages\n"
            f"- probability must be between 0.0 and 1.0\n"
            f"- rationale must cite specific file names and historical percentages\n\n"
            f"Respond with ONLY valid JSON object, no markdown, no code fences, no explanation:\n"
            f"{json_template}"
        )

        try:
            from app.services import watsonx_client
            raw = watsonx_client.generate(prompt, max_tokens=1024)

            # Step 5: parse JSON
            parsed: dict | None = None
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                match = re.search(r"\{.*\}", raw, re.DOTALL)
                if match:
                    try:
                        parsed = json.loads(match.group())
                    except json.JSONDecodeError:
                        parsed = None

            if parsed:
                sp_raw = parsed.get("stage_predictions", {})
                llm_stage_predictions = {
                    stage: StagePrediction(
                        probability=float(sp_raw[stage].get("probability", 0.5)),
                        rationale=str(sp_raw[stage].get("rationale", "")),
                    )
                    for stage in build_dna.PIPELINE_STAGES
                    if stage in sp_raw
                }
                llm_overall_risk = parsed.get("overall_risk")
                llm_summary = parsed.get("summary")

        except Exception:
            pass  # fall through to statistical fallback

    # If LLM path failed or was skipped, use statistical fallback
    if not llm_stage_predictions:
        rationale_suffix = (
            "Based on historical failure rates (LLM unavailable)."
            if not WATSONX_API_KEY
            else "Based on historical failure rates only."
        )
        llm_stage_predictions = _statistical_prediction(failure_rates, rationale_suffix)

    # Step 8: overall_risk (re-compute from actual probabilities to be authoritative)
    overall_risk = _compute_overall_risk(llm_stage_predictions)

    # Step 6 & 7: persist to Cloudant (skip gracefully if not configured)
    run_id = "local-fallback"
    prediction_doc_id = "local-fallback"
    try:
        run_id = build_dna.create_build_run(
            repo_id, commit_sha, author, branch, changed_files
        )
        stage_dict = {
            stage: {
                "probability": sp.probability,
                "rationale": sp.rationale,
            }
            for stage, sp in llm_stage_predictions.items()
        }
        prediction_doc_id = build_dna.save_prediction(
            run_id, repo_id, stage_dict, history_depth
        )
        # Mark the build run as "predicted" with the prediction linked
        build_dna.update_build_run_status(run_id, "predicted", prediction_doc_id)
    except RuntimeError:
        pass  # Cloudant not configured — run in local-fallback mode

    summary = llm_summary or (
        f"Prediction generated from {history_depth} prior build(s) of {repo_id}. "
        f"Overall risk is {overall_risk} based on historical failure rates."
    )

    # Step 9: return result
    return PredictionResult(
        run_id=run_id,
        commit_sha=commit_sha,
        repo_id=repo_id,
        changed_files=changed_files,
        stage_predictions=llm_stage_predictions,
        overall_risk=overall_risk,
        summary=summary,
        history_depth=history_depth,
        prediction_doc_id=prediction_doc_id,
    )
