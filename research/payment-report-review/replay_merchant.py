"""Replay archived merchant trials. Pass the ZIP path as the only argument."""
import argparse
from collections import Counter
import json
from zipfile import ZipFile

from review_merchant import ARMS, MODELS, SEEDS, grade, request


def replay(path):
    strict, aliases = Counter(), Counter()
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(MODELS) * len(SEEDS) * len(ARMS):
            raise ValueError("Unexpected archive size")
        for model in MODELS:
            for seed in SEEDS:
                for arm in ARMS:
                    name = f"{model.replace(':', '-')}-{seed}-{arm}.json"
                    record = json.loads(archive.read(name))
                    if record["metadata"]["request"] != request(model, seed, arm):
                        raise ValueError(f"Request mismatch in {name}")
                    result = grade(record["response"])
                    if result != record["result"]:
                        raise ValueError(f"Score mismatch in {name}")
                    strict[result["status"]] += 1
                    strict["detected"] += result["detected"]
                    if result.get("error") != "'rows'":
                        continue
                    obj = json.loads(record["response"]["message"]["content"])
                    if "input" not in obj:
                        continue
                    obj["rows"] = obj.pop("input")
                    diagnostic = grade({"message": {"content": json.dumps(obj)}})
                    aliases[diagnostic["status"]] += 1
                    for metric in ("distinguishes", "correct_expected", "detected"):
                        aliases[metric] += diagnostic.get(metric, False)
    return {"strict": dict(strict), "input_key_only_diagnostic": dict(aliases)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive")
    print(json.dumps(replay(parser.parse_args().archive), indent=2))
