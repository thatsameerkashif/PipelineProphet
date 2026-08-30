"""
Standalone test script for the prediction engine.

Works with or without IBM credentials:
  - No Cloudant: prints a warning, uses local-fallback run_id/prediction_doc_id
  - No watsonx.ai: prints a warning, uses statistical fallback from Build DNA rates
  - Neither: full fallback mode with placeholder data

Usage:
    python backend/scripts/test_prediction_engine.py
"""

import sys
import os

# Allow running from repo root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
# Resolve 'app' as 'backend/app'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import CLOUDANT_URL, CLOUDANT_APIKEY, WATSONX_API_KEY
from app.services import prediction_engine

# -- Credential status banner -----------------------------------------------

print("=" * 60)
print("Pipeline Prophet - Prediction Engine Test")
print("=" * 60)

if not CLOUDANT_URL or not CLOUDANT_APIKEY:
    print(
        "[WARNING] Cloudant credentials not configured.\n"
        "          Skipping Cloudant persistence - run_id and\n"
        "          prediction_doc_id will show 'local-fallback'.\n"
        "          Historical failure rates will default to 0.5.\n"
    )
else:
    print("[OK] Cloudant credentials found.")

if not WATSONX_API_KEY:
    print(
        "[WARNING] WATSONX_API_KEY not configured.\n"
        "          Granite LLM call will be skipped.\n"
        "          Predictions will use statistical fallback only.\n"
    )
else:
    print("[OK] watsonx.ai API key found.")

print()

# -- Run prediction ---------------------------------------------------------

TEST_REPO_ID = "pipeline-prophet-demo"
TEST_COMMIT  = "abc123test"
TEST_AUTHOR  = "sameer"
TEST_BRANCH  = "main"
TEST_FILES   = ["requirements.txt", "src/main.py"]

print(f"Running prediction for repo='{TEST_REPO_ID}' commit='{TEST_COMMIT}'")
print(f"Changed files: {TEST_FILES}")
print()

try:
    result = prediction_engine.predict(
        repo_id=TEST_REPO_ID,
        commit_sha=TEST_COMMIT,
        author=TEST_AUTHOR,
        branch=TEST_BRANCH,
        changed_files=TEST_FILES,
    )
except Exception as exc:
    print(f"[ERROR] prediction_engine.predict() raised an unexpected exception:")
    print(f"        {type(exc).__name__}: {exc}")
    sys.exit(1)

# -- Print results ----------------------------------------------------------

print("-" * 60)
print("PREDICTION RESULT")
print("-" * 60)
print(f"  run_id             : {result.run_id}")
print(f"  prediction_doc_id  : {result.prediction_doc_id}")
print(f"  repo_id            : {result.repo_id}")
print(f"  commit_sha         : {result.commit_sha}")
print(f"  history_depth      : {result.history_depth}")
print(f"  overall_risk       : {result.overall_risk}")
print()
print("  Per-stage probabilities:")
for stage, sp in result.stage_predictions.items():
    bar_len = int(sp.probability * 20)
    bar = "#" * bar_len + "." * (20 - bar_len)
    print(f"    {stage:<8}  {sp.probability:.2f}  [{bar}]")
    print(f"             rationale: {sp.rationale}")
print()
print(f"  Summary: {result.summary}")
print("-" * 60)
print()
print("[PASS] test_prediction_engine.py completed without errors.")
