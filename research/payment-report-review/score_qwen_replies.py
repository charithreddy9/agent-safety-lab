"""Check saved Qwen author replies offline using the original scorer."""
import json
from collections import Counter
from pathlib import Path
import sqlite3

from bounded_audit import histories
from study import FIXTURES, execute, oracle


def assess(sql, cases):
    counts = Counter()
    first_error = None
    for rows in cases:
        expected = oracle(rows)
        try:
            actual = execute(sql, rows)
        except (sqlite3.Error, ValueError, OverflowError) as exc:
            counts["execution_or_output_error"] += 1
            if first_error is None:
                first_error = str(exc)
            continue
        if actual == expected:
            counts["correct"] += 1
        elif sum(v for _, v in actual) == sum(v for _, v in expected):
            counts["wrong_breakdown_same_total"] += 1
        else:
            counts["wrong_total"] += 1
    return dict(counts=counts, first_error=first_error)


def evaluate(content):
    try:
        obj = json.loads(content)
    except json.JSONDecodeError as exc:
        return {"response_error": str(exc)}
    if not isinstance(obj, dict):
        return {"response_error": "Expected a JSON object"}
    sql = obj.get("sql")
    if not isinstance(sql, str) or not sql.strip():
        return {"response_error": "Missing or empty SQL string", "keys": sorted(obj)}
    return {"fixtures": assess(sql, FIXTURES), "bounded_histories": assess(sql, histories())}


if __name__ == "__main__":
    for seed in range(1, 5):
        path = Path("qwen-author-followup") / f"seed{seed}.json"
        record = json.loads(path.read_text(encoding="utf8"))
        print(json.dumps({"seed": seed, **evaluate(record["response"]["message"]["content"])}))
