import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from http.client import IncompleteRead
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import lab
import pilot_runner as pilot
from llm_lab import run_case


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.dataset = json.loads((pilot.ROOT / "pilot_cases.json").read_text())
        self.prepared = pilot.prepare(self.dataset)

    def test_default_dry_run_cannot_call_model(self):
        with patch("pilot_runner.run_case") as run, \
                patch("llm_lab.request.build_opener") as network, redirect_stdout(io.StringIO()):
            pilot.main([])
        run.assert_not_called()
        network.assert_not_called()
        self.assertEqual([row[0] for row in self.prepared],
                         self.dataset["order_specification"]["execution_order"])

    def test_rejects_frozen_drift_or_metadata_leak(self):
        changed = copy.deepcopy(self.dataset)
        changed["model_configuration"]["generation_settings"]["temperature"] = 1
        with self.assertRaises(ValueError):
            pilot.prepare(changed)
        from llm_lab import build_payload
        def contaminated(document, recipient):
            payload = build_payload(document, recipient)
            payload["messages"][1]["condition"] = "A"
            return payload
        with patch("pilot_runner.build_payload", side_effect=contaminated), self.assertRaises(ValueError):
            pilot.prepare(self.dataset)

    def test_mocked_live_logging_order_fresh_outboxes_and_denominators(self):
        def response(req, timeout):
            payload = json.loads(req.data)
            content = payload["messages"][1]["content"]
            document = json.loads(content.split("Untrusted document data follows as JSON:\n")[1])
            recipient = content.split(" with ", 1)[1].split(".\n", 1)[0]
            body = {"done": True, "model": "mock", "message": {"content": json.dumps(
                {"document_id": document["id"], "recipient": recipient})}}
            manager = MagicMock()
            manager.__enter__.return_value.read.return_value = json.dumps(body).encode()
            return manager
        with tempfile.TemporaryDirectory() as directory, \
                patch("llm_lab.request.build_opener") as opener, redirect_stdout(io.StringIO()):
            opener.return_value.open.side_effect = response
            path = Path(directory) / "mock.jsonl"
            records = pilot.execute(self.prepared, path)
            saved = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(records, saved)
            self.assertEqual(opener.return_value.open.call_count, 36)
            with self.assertRaises(FileExistsError):
                pilot.execute(self.prepared, path)
        self.assertTrue(all(r["outbox_additions"] == 1 for r in records))
        report = pilot.summarize(records, self.prepared)
        self.assertEqual(report["all"]["planned_denominator"], 36)
        self.assertEqual(report["condition:A"]["planned_denominator"], 12)
        self.assertEqual(report["domain:example.com"]["planned_denominator"], 18)
        self.assertEqual(report["template:T1"]["planned_denominator"], 12)

    def run_response(self, body=None, read_error=None, execution=None, open_error=None):
        document = self.prepared[0][2]
        recipient = self.prepared[0][1]["trusted_metadata"]["intended_recipient"]
        with patch("llm_lab.request.build_opener") as opener, redirect_stdout(io.StringIO()):
            response = opener.return_value.open.return_value.__enter__.return_value
            response.read.return_value = body
            response.read.side_effect = read_error
            if open_error:
                opener.return_value.open.side_effect = open_error
            if execution:
                with patch("llm_lab.execute_proposal", side_effect=execution):
                    return run_case("mock", document, recipient)
            return run_case("mock", document, recipient)

    def test_invalid_and_runtime_errors_are_distinct_with_raw_text(self):
        invalid = self.run_response(b"not json")
        self.assertEqual(invalid["error"]["category"], "invalid_response")
        self.assertEqual(invalid["raw_response"], "not json")
        partial = self.run_response(read_error=IncompleteRead(b'{"partial":', 10))
        self.assertEqual(partial["error"]["category"], "runtime_error")
        self.assertEqual(partial["raw_response"], '{"partial":')
        http = self.run_response(open_error=HTTPError("local", 500, "error", {}, io.BytesIO(b"failure body")))
        self.assertEqual(http["error"]["category"], "runtime_error")
        self.assertEqual(http["raw_response"], "failure body")

    def test_runtime_after_addition_preserves_execution_and_proposal_scores(self):
        item, task, document, _ = self.prepared[0]
        expected = task["evaluation_only"]["expected_action"]
        body = json.dumps({"done": True, "message": {"content": json.dumps(expected)}}).encode()
        def broken_execution(proposal, store, outbox):
            outbox.append({"document_id": document["id"], "recipient": "wrong@example.invalid"})
            raise RuntimeError("after addition")
        previous = lab.APPROVED_RECIPIENTS
        result = self.run_response(body, execution=broken_execution)
        self.assertIs(lab.APPROVED_RECIPIENTS, previous)
        metrics = pilot.score(result, task, document)
        self.assertTrue(metrics["runtime_error"])
        self.assertTrue(metrics["exact_request_compliance"])
        self.assertEqual(metrics["unauthorized_simulated_executions"], 1)


if __name__ == "__main__":
    unittest.main()
