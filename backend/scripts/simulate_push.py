"""
Simulate a GitHub push webhook to the local Pipeline Prophet backend.

Usage:
    python -m backend.scripts.simulate_push
    # or from the backend/ directory:
    python scripts/simulate_push.py

Environment variables (override via .env or shell):
    BACKEND_URL           — default: http://localhost:8000
    GITHUB_WEBHOOK_SECRET — default: demo-secret
"""

import hashlib
import hmac
import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
WEBHOOK_SECRET: str = os.getenv("GITHUB_WEBHOOK_SECRET", "demo-secret")

# Simulates a push that touches requirements.txt and src/main.py (high-risk combo)
payload = {
    "ref": "refs/heads/main",
    "after": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3",
    "pusher": {"name": "sameer"},
    "repository": {"name": "pipeline-prophet-demo"},
    "commits": [
        {
            "id": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3",
            "message": "Update dependencies and refactor main handler",
            "added": [],
            "modified": ["requirements.txt", "src/main.py"],
            "removed": [],
        }
    ],
}

payload_bytes: bytes = json.dumps(payload).encode()

# Correct Python 3 HMAC: hmac.new(key, msg, digestmod)
sig: str = "sha256=" + hmac.new(
    WEBHOOK_SECRET.encode(), payload_bytes, hashlib.sha256
).hexdigest()

print(f"Sending simulated push to {BACKEND_URL}/api/webhook …")
response = httpx.post(
    f"{BACKEND_URL}/api/webhook",
    content=payload_bytes,
    headers={
        "Content-Type": "application/json",
        "X-GitHub-Event": "push",
        "X-Hub-Signature-256": sig,
    },
)
print(f"Webhook response: {response.status_code} — {response.json()}")
