"""Recompute Table 1 from the archived final answers using standard Python."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from zipfile import ZipFile

import review_merchant
import review_supplied
from run_pilot import MODELS, SEEDS

ROOT = Path(__file__).resolve().parent
GRADERS = {"refund": review_supplied.grade, "merchant": review_merchant.grade}


def reproduce(records):
    expected = {(policy, model, seed, arm) for policy in GRADERS
                for model in MODELS for seed in SEEDS for arm in review_supplied.ARMS}
    counts = defaultdict(Counter)
    for trial in records:
        policy, model, seed, arm = (trial[k] for k in ("policy", "model", "seed", "arm"))
        key = policy, model, seed, arm
        if key not in expected:
            raise ValueError(f"Duplicate or unexpected trial: {key}")
        expected.remove(key)
        score = GRADERS[policy]({"message": {"content": trial["answer"]}})
        counts[policy, model, arm].update(
            attempts=1, scorable=int(score["status"] == "scored"),
            distinguishes=int(score.get("distinguishes", False)), detections=int(score["detected"]))
    if expected:
        raise ValueError(f"Missing trials: {sorted(expected)}")
    archived = json.loads((ROOT / "controlled-results.json").read_text(encoding="utf8"))
    for (policy, model, arm), cell in counts.items():
        if dict(cell) != archived[policy]["by_arm"][model][arm]:
            raise ValueError(f"Replayed counts differ for {policy}, {model}, {arm}")
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replication_zip", type=Path)
    args = parser.parse_args()
    records = []
    with ZipFile(args.replication_zip) as archive:
        for policy in GRADERS:
            records.extend(dict(row, policy=policy) for row in json.loads(archive.read(policy + ".json")))
    counts = reproduce(records)
    print("Policy | Model | SQL shown | SQL hidden")
    print("Counts per five attempts: scorable / exposed / detected")
    for policy in GRADERS:
        for model in MODELS:
            cells = []
            for arm in review_supplied.ARMS:
                count = counts[policy, model, arm]
                cells.append(" / ".join(str(count[m]) for m in ("scorable", "distinguishes", "detections")))
            print(" | ".join([policy, model, *cells]))
