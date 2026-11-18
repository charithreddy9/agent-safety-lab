"""Paired test design with the supplied refund-date query visible or hidden."""
import json
import sqlite3
from collections import Counter
from pathlib import Path
from urllib.error import URLError

from run_pilot import MODELS, SEEDS, inventory
from study import FAULT, GOOD, POLICY, REVIEW, SCHEMA, post, score

ARMS = ("visible", "hidden")


def request_for(model, seed, arm):
    parts = [POLICY, SCHEMA]
    if arm == "visible":
        parts.append("Report implementation:\n" + FAULT)
    parts.append(REVIEW)
    request = dict(model=model, messages=[dict(role="user", content="\n\n".join(parts))],
                   stream=False, format="json", options=dict(seed=seed, temperature=0.3, num_predict=1200))
    if model == "qwen3:4b":
        request["think"] = False
    return request


def grade(response):
    try:
        test = json.loads(response["message"]["content"])
        reference = score(GOOD, test)
        candidate = score(FAULT, test)
    except (KeyError, ValueError, TypeError, OverflowError, sqlite3.Error) as exc:
        return dict(status="invalid_test", error=str(exc), detected=False)
    assert not reference["distinguishes"]
    return dict(status="scored", correct_expected=reference["correct_expected"],
                distinguishes=candidate["distinguishes"], detected=candidate["detects_balanced_error"])


def run(folder):
    tags = {item["name"]: item["digest"] for item in inventory("tags")["models"]}
    version = inventory("version")
    if any(model not in tags for model in MODELS):
        raise SystemExit("Both pilot models must be installed.")
    folder.mkdir(exist_ok=True, parents=True)
    summary = {}
    for model in MODELS:
        pairs = Counter()
        invalid = Counter()
        for seed in SEEDS:
            results = {}
            for arm in (ARMS if seed % 2 else reversed(ARMS)):
                path = folder / f"{model.replace(':','-')}-{seed}-{arm}.json"
                request = request_for(model, seed, arm)
                metadata = dict(model_digest=tags[model], ollama_version=version, request=request)
                if path.exists():
                    record = json.loads(path.read_text(encoding="utf8"))
                    if record["metadata"] != metadata:
                        raise SystemExit(f"Saved settings differ for {path}.")
                else:
                    print(f"{model} seed {seed} {arm}", flush=True)
                    record = dict(metadata=metadata)
                    try:
                        record["response"] = post("chat", request)
                        record["result"] = grade(record["response"])
                    except (URLError, TimeoutError) as exc:
                        record["result"] = dict(status="request_error", error=str(exc))
                    with path.open("x", encoding="utf8") as handle:
                        json.dump(record, handle)
                results[arm] = record["result"]
                if results[arm]["status"] == "invalid_test":
                    invalid[arm] += 1
            if any(r["status"] == "request_error" for r in results.values()):
                pairs["incomplete"] += 1
            else:
                hits = [arm for arm in ARMS if results[arm]["detected"]]
                category = "both" if len(hits) == 2 else "neither"
                if len(hits) == 1:
                    category = hits[0] + "_only"
                pairs[category] += 1
        summary[model] = dict(pairs=dict(pairs), invalid_tests=dict(invalid))
    return summary


if __name__ == "__main__":
    print(json.dumps(run(Path("supplied-query-trials")), indent=2))
