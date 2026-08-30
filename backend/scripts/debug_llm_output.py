#!/usr/bin/env python3
"""Test raw LLM output to see what Llama-3.3-70B returns."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import watsonx_client

prompt = (
    "You are a CI/CD failure prediction system.\n"
    "Repository: pipeline-prophet-demo\n"
    "Changed files: requirements.txt, src/main.py\n"
    "Historical evidence from 80 builds:\n"
    "- requirements.txt -> install stage: failed 72% of 18 runs\n"
    "- requirements.txt -> test stage: failed 35% of 18 runs\n"
    "- src/main.py -> lint stage: failed 45% of 12 runs\n"
    "- src/main.py -> test stage: failed 28% of 12 runs\n\n"
    "Respond with ONLY valid JSON object, no markdown, no code fences, no explanation:\n"
    '{"stage_predictions":{"install":{"probability":0.0,"rationale":"string"},'
    '"test":{"probability":0.0,"rationale":"string"},'
    '"lint":{"probability":0.0,"rationale":"string"},'
    '"build":{"probability":0.0,"rationale":"string"}},'
    '"overall_risk":"HIGH","summary":"string"}'
)

print("Sending prompt to watsonx.ai Llama-3.3-70B...")
raw = watsonx_client.generate(prompt, max_tokens=700)
print()
print("=== RAW OUTPUT ===")
print(repr(raw))
print()
print("=== DISPLAY ===")
print(raw)
