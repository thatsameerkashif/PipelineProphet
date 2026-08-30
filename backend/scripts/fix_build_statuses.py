#!/usr/bin/env python3
"""
fix_build_statuses.py
---------------------
Updates existing build_run documents in Cloudant to have realistic
status/outcome values (not all "pending").

Run once:
    python backend/scripts/fix_build_statuses.py
"""
import sys, os, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

random.seed(77)

from app.config import CLOUDANT_URL
from app.services.cloudant_client import client
from app.services.build_dna import get_db_name
from ibmcloudant.cloudant_v1 import Document

if not CLOUDANT_URL or client is None:
    print("Cloudant not configured.")
    sys.exit(1)

db = get_db_name("build_runs")

# Fetch all build_run docs
result = client.post_find(
    db=db,
    selector={"repo_id": "pipeline-prophet-demo"},
    limit=500,
).get_result()

docs = result.get("docs", [])
print(f"Found {len(docs)} build_run documents")

# Statuses for seeded/debug docs — realistic distribution
# 60% passed, 30% failed, 10% predicted (recent)
status_pool = (["passed"] * 12 + ["failed"] * 6 + ["predicted"] * 2)

updated = 0
for i, doc in enumerate(docs):
    current = doc.get("outcome", "pending")
    # Skip docs that already have a real status
    if current in ("passed", "failed", "predicted"):
        continue

    # Assign realistic status
    new_status = random.choice(status_pool)

    doc["outcome"] = new_status
    doc["status"] = new_status

    # Add realistic fields if missing
    if "author" not in doc:
        doc["author"] = random.choice(["sameer", "alice", "bob"])
    if "branch" not in doc:
        doc["branch"] = random.choice(["main", "feature/auth", "fix/bug-123"])
    if "commit_sha" not in doc:
        doc["commit_sha"] = "seed" + hex(random.randint(0, 0xFFFFFF))[2:].zfill(6) + "0000"
    if "changed_files" not in doc:
        doc["changed_files"] = random.sample(
            ["requirements.txt", "src/main.py", "tests/test_main.py", "Dockerfile", "src/config.py"],
            k=random.randint(1, 3)
        )
    if "started_at" not in doc:
        from datetime import datetime, timezone, timedelta
        doc["started_at"] = (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 80))).isoformat()

    try:
        client.post_document(db=db, document=Document.from_dict(doc))
        updated += 1
    except Exception as e:
        print(f"  WARN: could not update {doc.get('_id', '?')[:12]}: {e}")

print(f"Updated {updated} documents with realistic statuses.")
print("Done.")
