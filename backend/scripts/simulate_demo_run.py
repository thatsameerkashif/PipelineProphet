"""
simulate_demo_run.py
--------------------
End-to-end demo of the Pipeline Prophet prediction + accuracy feedback loop.

Steps:
  1. POST webhook payload (requirements.txt + src/main.py changes)
  2. Wait 2 s
  3. GET /api/repos/{REPO_ID}/latest-prediction
  4. POST /api/builds/{run_id}/outcome with actual results
  5. Print accuracy metrics and a human-readable summary

Usage:
    python backend/scripts/simulate_demo_run.py
    python backend/scripts/simulate_demo_run.py --base-url http://localhost:8000
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

# Load .env so GITHUB_WEBHOOK_SECRET is available
_env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")


def _sign_payload(payload_bytes: bytes) -> str:
    """Compute HMAC-SHA256 signature for the webhook payload."""
    if not WEBHOOK_SECRET:
        return "sha256=demo"
    sig = hmac.new(WEBHOOK_SECRET.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"

REPO_ID = "pipeline-prophet-demo"
ACTUAL_OUTCOMES = {
    "install": "failed",
    "test": "passed",
    "lint": "passed",
    "build": "passed",
}


def _post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _get(url: str, headers: dict | None = None) -> dict | None:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def main(base_url: str) -> None:
    commit_sha = "demo" + datetime.now(timezone.utc).strftime("%H%M%S%f")
    webhook_payload = {
        "ref": "refs/heads/main",
        "after": commit_sha,
        "pusher": {"name": "demo-user"},
        "repository": {"name": REPO_ID},
        "commits": [{"added": [], "modified": ["requirements.txt", "src/main.py"], "removed": []}],
    }

    # ── Step 1: trigger webhook ────────────────────────────────────────────
    print("Step 1 — Triggering webhook…")
    payload_bytes = json.dumps(webhook_payload).encode()
    webhook_headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "push",
        "X-Hub-Signature-256": _sign_payload(payload_bytes),
    }
    req = urllib.request.Request(
        f"{base_url}/api/webhook",
        data=payload_bytes,
        headers=webhook_headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        webhook_resp = json.loads(resp.read())
    run_id = webhook_resp.get("run_id", "unknown")
    print(f"  run_id = {run_id}")

    # ── Step 2: poll for prediction (LLM may take up to 15s) ──────────────
    print("Step 2 — Polling for prediction (LLM call in progress, up to 15s)…")
    prediction = None
    for attempt in range(15):
        time.sleep(2)
        prediction = _get(f"{base_url}/api/repos/{REPO_ID}/latest-prediction")
        if prediction:
            print(f"  Got prediction after {(attempt+1)*2}s")
            break
        print(f"  Waiting… ({(attempt+1)*2}s elapsed)")

    # ── Step 3: show prediction ────────────────────────────────────────────
    print("Step 3 — Prediction result…")
    if not prediction:
        print("  No prediction arrived in 30s — server may be overloaded.")
    else:
        pred_run_id = prediction.get("run_id", run_id)
        run_id = pred_run_id  # use the prediction's own run_id for outcome POST
        print(f"  Prediction for run_id={run_id}:")
        for stage, info in prediction.get("stage_predictions", {}).items():
            prob = info.get("probability", "?")
            risk = info.get("risk", "?")
            print(f"    {stage:10s}: probability={prob:.2f}  risk={risk}")

    # ── Step 4: post actual outcomes ───────────────────────────────────────
    print("\nStep 4 — Posting actual outcomes…")
    outcome_resp = _post(
        f"{base_url}/api/builds/{run_id}/outcome",
        {"actual_outcomes": ACTUAL_OUTCOMES},
    )
    print("  Response:", json.dumps(outcome_resp, indent=4))

    # ── Step 5: summary ────────────────────────────────────────────────────
    print("\nStep 5 — Summary")
    errors = outcome_resp.get("absolute_errors", {})
    mae = outcome_resp.get("mean_absolute_error", "?")
    stage_preds = outcome_resp.get("stage_predictions", {})

    for stage, actual_str in ACTUAL_OUTCOMES.items():
        info = stage_preds.get(stage, {})
        prob = info.get("probability", None)
        risk = info.get("risk", "?")
        err = errors.get(stage, "?")
        is_high_risk = isinstance(prob, (int, float)) and prob >= 0.5
        risk_label = "HIGH risk" if is_high_risk else "low risk"
        print(
            f"  Prediction was {risk_label} for '{stage}' stage.  "
            f"Actual: {stage} {actual_str.upper()}.  "
            f"Absolute error: {err}"
        )

    accuracy_pct = round((1 - float(mae)) * 100, 1) if isinstance(mae, (int, float)) else "?"
    print(f"\n  Overall MAE: {mae}  ->  Accuracy: {accuracy_pct}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    main(args.base_url)
