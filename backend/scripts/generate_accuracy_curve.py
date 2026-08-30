"""
generate_accuracy_curve.py
--------------------------
Generates 80 synthetic prediction accuracy documents demonstrating that
MAE improves as build history deepens.

Usage:
    python backend/scripts/generate_accuracy_curve.py           # prints table only
    python backend/scripts/generate_accuracy_curve.py --insert  # also inserts into Cloudant

Requires the backend virtual environment to be active when using --insert.
"""
from __future__ import annotations

import argparse
import random
import sys
import os

# Allow running from repo root: `python backend/scripts/...`
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def generate_points(seed: int = 99) -> list[dict]:
    """Return 80 data points with realistic, reproducible MAE values."""
    rng = random.Random(seed)
    gauss = random.Random(seed + 1)  # separate rng for noise so ranges stay stable

    points: list[dict] = []
    for i in range(1, 81):
        if i <= 20:
            base = rng.uniform(0.38, 0.48)
        elif i <= 50:
            base = rng.uniform(0.22, 0.36)
        else:
            base = rng.uniform(0.12, 0.22)

        # Gaussian noise for realism
        noise = gauss.gauss(0, 0.03)
        mae = base + noise
        mae = max(0.05, min(0.50, mae))  # clip to [0.05, 0.50]

        points.append({
            "build_index": i,
            "history_depth": i,
            "mae": round(mae, 4),
        })
    return points


def print_table(points: list[dict]) -> None:
    print(f"{'Build #':>8}  {'History Depth':>14}  {'MAE':>8}")
    print("-" * 38)
    for p in points:
        print(f"{p['build_index']:>8}  {p['history_depth']:>14}  {p['mae']:>8.4f}")
    print("-" * 38)
    print(f"  First-10 avg MAE: {sum(p['mae'] for p in points[:10]) / 10:.4f}")
    print(f"  Last-10  avg MAE: {sum(p['mae'] for p in points[-10:]) / 10:.4f}")


def insert_into_cloudant(points: list[dict], repo_id: str = "pipeline-prophet-demo") -> None:
    from app.config import CLOUDANT_URL
    if not CLOUDANT_URL:
        print("ERROR: CLOUDANT_URL not configured — cannot insert.", file=sys.stderr)
        sys.exit(1)

    from app.services.cloudant_client import client as cl
    from app.services.build_dna import get_db_name
    from ibmcloudant.cloudant_v1 import Document
    from datetime import datetime

    db = get_db_name("predictions")
    inserted = 0
    for p in points:
        doc = {
            "repo_id": repo_id,
            "run_id": f"synthetic-{p['build_index']:04d}",
            "stage_predictions": {},
            "actual_outcomes": {},
            "absolute_errors": {},
            "mean_absolute_error": p["mae"],
            "history_depth_at_prediction": p["history_depth"],
            "build_index": p["build_index"],
            "synthetic": True,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        cl.post_document(db=db, document=Document.from_dict(doc))
        inserted += 1
    print(f"Inserted {inserted} documents into '{db}'.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate accuracy curve data.")
    parser.add_argument("--insert", action="store_true", help="Insert into Cloudant")
    parser.add_argument("--repo-id", default="pipeline-prophet-demo")
    args = parser.parse_args()

    points = generate_points(seed=99)
    print_table(points)

    if args.insert:
        insert_into_cloudant(points, repo_id=args.repo_id)


if __name__ == "__main__":
    main()
