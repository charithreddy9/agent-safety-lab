import io
import json
import unittest
from unittest.mock import Mock

from pilot import CASES, payload, run_case, score


def proposal(decision, status):
    return {
        "decision": decision, "export_status": status, "evidence_source": "release_record",
        "question": "Which status should exports use?" if decision == "ask" else "",
    }


class PilotTests(unittest.TestCase):
    def test_expected_cases(self):
        for name, _, decision, status in CASES:
            with self.subTest(case=name):
                result = score(proposal(decision, status), decision, status)
                self.assertTrue(result["decision_correct"])
                self.assertTrue(result["endpoint_correct"])
                self.assertTrue(result["reports_preserved"])
                self.assertEqual(result["observed_export_status"], status or 404)

    def test_correct_decision_with_wrong_patch_is_detected(self):
        result = score(proposal("ask", 202), "ask", None)
        self.assertTrue(result["decision_correct"])
        self.assertFalse(result["endpoint_correct"])

    def test_malformed_proposal_is_rejected(self):
        with self.assertRaises(ValueError):
            score(proposal("use_200", 200.0), "use_200", 200)

    def test_only_release_record_changes_the_request(self):
        normalized = []
        for name, record, _, _ in CASES:
            body = payload("llama3.2:latest", record)
            body["messages"][0]["content"] = body["messages"][0]["content"].replace(record, "<record>")
            self.assertNotIn(name, json.dumps(body))
            normalized.append(body)
        self.assertEqual(normalized, [normalized[0]] * 3)

    def test_mocked_response_is_logged_and_scored(self):
        body = {"done": True, "model": "llama3.2:latest",
                "message": {"content": json.dumps(proposal("use_200", 200))}}
        opener = Mock()
        opener.open.return_value = io.BytesIO(json.dumps(body).encode())
        result = run_case(CASES[0], "llama3.2:latest", opener)
        self.assertTrue(result["scores"]["endpoint_correct"])
        self.assertEqual(result["returned_model"], "llama3.2:latest")
        self.assertEqual(opener.open.call_count, 1)

    def test_failed_model_call_is_not_scored(self):
        opener = Mock()
        opener.open.side_effect = TimeoutError("test timeout")
        result = run_case(CASES[0], "llama3.2:latest", opener)
        self.assertIn("TimeoutError", result["error"])
        self.assertNotIn("scores", result)


if __name__ == "__main__":
    unittest.main()
