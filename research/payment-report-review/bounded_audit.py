"""Enumerate a finite domain of valid sales histories and audit two reports."""
from itertools import combinations_with_replacement
from collections import Counter
import json
from study import GOOD, FAULT, execute, oracle

def histories():
    days = ["2026-06-01", "2026-06-02", "2026-06-03"]
    choices = []
    for index, sold in enumerate(days):
        for price in (100, 200):
            choices.append((sold, price, None, 0))
            for refunded in days[index:]:
                for amount in range(100, price + 1, 100):
                    choices.append((sold, price, refunded, amount))
    for size in (1, 2):
        for group in combinations_with_replacement(choices, size):
            yield [[i, *sale] for i, sale in enumerate(group, 1)]

def audit():
    counts = Counter()
    for rows in histories():
        truth = oracle(rows)
        correct = execute(GOOD, rows)
        faulty = execute(FAULT, rows)
        counts["histories"] += 1
        counts["reference_agrees"] += correct == truth
        counts["total_check_detects"] += sum(v for _,v in faulty) != sum(v for _,v in truth)
        counts["daily_check_detects"] += faulty != truth
        cross_day = any(r[3] is not None and r[3] != r[1] for r in rows)
        counts["cross_day_histories"] += cross_day
        assert (faulty != truth) == cross_day
    return dict(counts)

if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
