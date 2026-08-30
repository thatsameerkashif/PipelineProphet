#!/usr/bin/env python3
"""Debug script to isolate prediction engine issues."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import watsonx_client, build_dna

# 1. Test watsonx directly
print("=== 1. watsonx.ai direct test ===")
try:
    result = watsonx_client.generate("Reply with only the word: hello", max_tokens=20)
    print("  PASS:", repr(result))
except Exception as e:
    print("  FAIL:", type(e).__name__, str(e))

# 2. Test Build DNA failure rates
print()
print("=== 2. Build DNA query_failure_rates ===")
try:
    rates = build_dna.query_failure_rates(
        "pipeline-prophet-demo", ["requirements.txt", "src/main.py"]
    )
    print("  PASS:", rates)
except Exception as e:
    print("  FAIL:", type(e).__name__, str(e))

# 3. Test create_build_run
print()
print("=== 3. Build DNA create_build_run ===")
try:
    run_id = build_dna.create_build_run(
        "pipeline-prophet-demo", "debugsha001", "sameer", "main", ["requirements.txt"]
    )
    print("  PASS run_id:", run_id)
except Exception as e:
    print("  FAIL:", type(e).__name__, str(e))

# 4. Full predict() call
print()
print("=== 4. Full predict() call ===")
try:
    from app.services.prediction_engine import predict
    result = predict(
        "pipeline-prophet-demo", "debugsha002", "sameer", "main",
        ["requirements.txt", "src/main.py"]
    )
    print("  run_id:", result.run_id)
    print("  overall_risk:", result.overall_risk)
    print("  history_depth:", result.history_depth)
    print("  prediction_doc_id:", result.prediction_doc_id)
    for stage, sp in result.stage_predictions.items():
        print(f"  {stage}: prob={sp.probability:.3f}  rationale={sp.rationale[:80]}")
except Exception as e:
    import traceback
    print("  FAIL:", type(e).__name__, str(e))
    traceback.print_exc()
