"""Merchant-attribution replication. Run from the research directory."""
import json
import sqlite3
from collections import Counter
from itertools import product, combinations_with_replacement
from pathlib import Path

from review_supplied import ARMS, run, request_for
from run_pilot import MODELS, SEEDS

FIELDS = ("id", "booking_merchant", "fulfilling_merchant", "amount_cents")
OUTPUT = ("merchant", "total_cents")
SCHEMA = "CREATE TABLE sales(id INTEGER PRIMARY KEY, booking_merchant TEXT, fulfilling_merchant TEXT, amount_cents INTEGER)"
POLICY = """For each settled sale, credit its full positive amount to the fulfilling merchant.
Return one row per merchant credited, with its total in integer cents. Ignore ordering.
IDs are distinct positive integers; merchant codes are nonempty strings."""
GOOD = "SELECT fulfilling_merchant, SUM(amount_cents) FROM sales GROUP BY fulfilling_merchant"
FAULT = GOOD.replace("fulfilling_merchant", "booking_merchant")
REVIEW = """Design one test. Return JSON with rows and expected. Supply 1 to 6 input rows
[id,booking_merchant,fulfilling_merchant,amount_cents] and the complete expected output
as [merchant,total_cents] pairs. Arrays or objects with the exact named fields are accepted."""


def request(model, seed, arm):
    payload = request_for(model, seed, arm)
    parts = [POLICY, SCHEMA]
    if arm == "visible":
        parts.append("Report implementation:\n" + FAULT)
    payload["messages"][0]["content"] = "\n\n".join(parts + [REVIEW])
    return payload


def fields(row, names):
    if isinstance(row, list) and len(row) == len(names):
        return tuple(row)
    if isinstance(row, dict) and set(row) == set(names):
        return tuple(row[name] for name in names)
    raise ValueError("missing or unexpected fields")


def reports(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 6:
        raise ValueError("invalid row count")
    sales = [fields(row, FIELDS) for row in rows]
    ids = set()
    totals = Counter()
    for ident, booking, fulfilling, amount in sales:
        if type(ident) is not int or ident <= 0 or ident in ids:
            raise ValueError("invalid sale ID")
        if not all(isinstance(code, str) and code.strip() for code in (booking, fulfilling)):
            raise ValueError("invalid merchant")
        if type(amount) is not int or amount <= 0:
            raise ValueError("invalid amount")
        ids.add(ident)
        totals[fulfilling] += amount
    db = sqlite3.connect(":memory:")
    try:
        db.execute(SCHEMA)
        db.executemany("INSERT INTO sales VALUES (?,?,?,?)", sales)
        correct, faulty = [sorted(db.execute(sql)) for sql in (GOOD, FAULT)]
    finally:
        db.close()
    assert correct == sorted(totals.items())
    assert sum(totals.values()) == sum(value for _, value in faulty)
    return correct, faulty


def grade(response):
    try:
        test = json.loads(response["message"]["content"])
        correct, faulty = reports(test["rows"])
    except (KeyError, TypeError, ValueError, OverflowError, sqlite3.Error) as exc:
        return dict(status="invalid_test", error=str(exc), detected=False)
    try:
        expected = test.get("expected")
        if not isinstance(expected, list):
            raise ValueError("missing expected list")
        pairs = [fields(row, OUTPUT) for row in expected]
        agrees = all(isinstance(m,str) and type(v) is int for m,v in pairs) and sorted(pairs) == correct
    except (ValueError, TypeError):
        agrees = False
    return dict(status="scored", distinguishes=correct != faulty, correct_expected=agrees,
                detected=correct != faulty and agrees)


def calibration():
    choices = list(product(("A","B"), ("A","B"), (100,200)))
    counts = Counter()
    for size in (1,2):
        for group in combinations_with_replacement(choices,size):
            rows = [[i,*sale] for i,sale in enumerate(group,1)]
            correct, faulty = reports(rows)
            counts["histories"] += 1
            counts["expose_fault"] += correct != faulty
    return dict(counts)


if __name__ == "__main__":
    folder = Path("merchant-review-trials")
    print("Calibration", calibration(), flush=True)
    paired = run(folder, request, grade)
    for model in MODELS:
        by_arm = {}
        for arm in ARMS:
            counts = Counter()
            for seed in SEEDS:
                path = folder / f"{model.replace(':','-')}-{seed}-{arm}.json"
                result = json.loads(path.read_text(encoding="utf8"))["result"]
                counts[result["status"]] += 1
                for metric in ("distinguishes", "correct_expected", "detected"):
                    counts[metric] += bool(result.get(metric))
            by_arm[arm] = dict(counts)
        paired[model]["by_arm"] = by_arm
    print(json.dumps(paired, indent=2))
