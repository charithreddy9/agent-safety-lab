"""Regenerate the primary results from the two original Ollama trial ZIPs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import review_merchant
import review_supplied
from run_pilot import MODELS, SEEDS


def replay(path, make_request, grade):
    arms = review_supplied.ARMS
    trials = {f"{model.replace(':', '-')}-{seed}-{arm}.json": (model, seed, arm)
              for model in MODELS for seed in SEEDS for arm in arms}
    counts = {}
    hits = {}
    inventories = {}
    stops = Counter()
    with ZipFile(path) as archive:
        if sorted(archive.namelist()) != sorted(trials):
            raise ValueError(f"{path}: missing, duplicate or unexpected trial files")
        for name, (model, seed, arm) in trials.items():
            record = json.loads(archive.read(name))
            meta = record["metadata"]
            if meta["request"] != make_request(model, seed, arm):
                raise ValueError(f"{name}: request differs from protocol")
            inventory = (meta["model_digest"], meta["ollama_version"]["version"])
            if inventories.setdefault(model, inventory) != inventory:
                raise ValueError(f"{name}: model digest or runtime changed")
            response = record["response"]
            if response["model"] != model or response["done"] is not True:
                raise ValueError(f"{name}: incomplete or mismatched model response")
            stops[response["done_reason"]] += 1
            score = grade(response)
            if score != record["result"]:
                raise ValueError(f"{name}: replay differs from saved score")
            cell = counts.setdefault(model, {}).setdefault(arm, Counter())
            cell.update(attempts=1, scorable=int(score["status"] == "scored"),
                        distinguishes=int(score.get("distinguishes", False)),
                        detections=int(score["detected"]))
            hits[model, seed, arm] = score["detected"]
    pairs = {}
    for model in MODELS:
        categories = Counter(dict.fromkeys(("both", "visible_only", "hidden_only", "neither"), 0))
        for seed in SEEDS:
            visible, hidden = (hits[model, seed, arm] for arm in arms)
            categories[{(True, True): "both", (True, False): "visible_only",
                        (False, True): "hidden_only", (False, False): "neither"}[visible, hidden]] += 1
        pairs[model] = categories
    return dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                digest_and_runtime=inventories, stop_reasons=stops, by_arm=counts, pairs=pairs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("refund_archive", type=Path)
    parser.add_argument("merchant_archive", type=Path)
    args = parser.parse_args()
    results = {
        "refund": replay(args.refund_archive, review_supplied.request_for, review_supplied.grade),
        "merchant": replay(args.merchant_archive, review_merchant.request, review_merchant.grade),
    }
    print(json.dumps(results, indent=2))
