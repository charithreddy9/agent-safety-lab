"""Replay the exploratory named-field diagnostic from the refund trial ZIP."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from zipfile import ZipFile

from replay_controlled import replay
from review_supplied import grade, request_for

SALE_FIELDS = ("id", "sale_day", "sale_cents", "refund_day", "refund_cents")
OUTPUT_FIELDS = ("day", "net_cents")


def positional(rows, fields):
    if isinstance(rows, list):
        return [[row[key] for key in fields]
                if isinstance(row, dict) and set(row) == set(fields) else row
                for row in rows]
    return rows


def diagnose(path):
    primary = replay(path, request_for, grade)
    counts = defaultdict(Counter)
    payloads = defaultdict(set)
    with ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            record = json.loads(archive.read(name))
            request = record["metadata"]["request"]
            arm = name.rsplit("-", 1)[1].removesuffix(".json")
            group = (request["model"], arm)
            count = counts[group]
            count["attempted"] += 1
            if record["result"]["status"] != "invalid_test":
                continue
            count["strict_invalid"] += 1
            try:
                test = json.loads(record["response"]["message"]["content"])
            except json.JSONDecodeError:
                continue
            if not isinstance(test, dict):
                continue
            converted = dict(test)
            for key, fields in (("rows", SALE_FIELDS), ("expected", OUTPUT_FIELDS)):
                if key in test:
                    converted[key] = positional(test[key], fields)
            if converted == test:
                continue
            canonical = json.dumps(converted, sort_keys=True)
            score = grade({"message": {"content": canonical}})
            if score["status"] == "scored":
                payloads[group].add(canonical)
                count["recovered"] += 1
                for metric in ("distinguishes", "correct_expected", "detected"):
                    count[metric] += int(score[metric])
    metrics = ("attempted", "strict_invalid", "recovered", "distinguishes",
               "correct_expected", "detected")
    groups = [dict(model=model, arm=arm, **{m: count[m] for m in metrics},
                   distinct_recovered_payloads=len(payloads[model, arm]))
              for (model, arm), count in sorted(counts.items())]
    return dict(archive_sha256=primary["sha256"], exploratory_by_arm=groups)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("refund_archive", type=Path)
    print(json.dumps(diagnose(parser.parse_args().refund_archive), indent=2))
