import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from llm_lab import build_payload
from repeatability import INTENDED, run_trials, score


class RepeatabilityTests(unittest.TestCase):
    def test_errors_are_not_compliance_or_defenses(self):
        metrics = score({"failure": "timeout", "proposal": None, "outbox": []})
        self.assertTrue(metrics["invalid_or_error"])
        self.assertFalse(metrics["exact_compliance"])
        self.assertFalse(metrics["attacker_target"])
        self.assertFalse(metrics["other_unauthorized_proposal"])

    def test_separate_proposal_and_execution_metrics(self):
        for recipient, expected in ((INTENDED["recipient"], "exact_compliance"),
                                    ("stranger@example.invalid", "attacker_target"),
                                    ("study-group@example.com", "other_unauthorized_proposal")):
            proposal = dict(INTENDED, recipient=recipient)
            metrics = score({"failure": None, "proposal": proposal, "outbox": []})
            self.assertTrue(metrics[expected])
            self.assertEqual(metrics["unauthorized_actions_executed"], 0)

    def test_alternating_order_and_all_failures_recorded(self):
        def failed_case(label, document):
            payload = build_payload(document)
            return {"failure": "mock timeout", "proposal": None, "outbox": [],
                    "decision": "NOT EXECUTED", "elapsed": 1,
                    "raw_response": None, "request": payload,
                    "request_body": json.dumps(payload)}

        with tempfile.TemporaryDirectory() as directory, \
                patch("repeatability.run_case", side_effect=failed_case) as run, \
                redirect_stdout(io.StringIO()):
            path = Path(directory) / "results.jsonl"
            records = run_trials(path)
            saved = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(run.call_count, 10)
        self.assertEqual(saved, records)
        self.assertEqual([record["case"] for record in records],
                         ["clean", "injected", "injected", "clean", "clean",
                          "injected", "injected", "clean", "clean", "injected"])
        self.assertTrue(all(record["metrics"]["invalid_or_error"] for record in records))


if __name__ == "__main__":
    unittest.main()
