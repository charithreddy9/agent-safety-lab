import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import lab
from controlled_followup import HARMLESS, INJECTION, conditions, metrics
from llm_lab import build_payload, run_case


class ControlledFollowupTests(unittest.TestCase):
    def test_matched_inputs(self):
        documents = conditions()
        self.assertLess(abs(len(HARMLESS) - len(INJECTION)), 10)
        self.assertNotIn("@", HARMLESS)
        self.assertEqual(documents["B"]["text"], documents["A"]["text"] + "\n" + HARMLESS)
        self.assertEqual(documents["C"]["text"], documents["A"]["text"] + "\n" + INJECTION)
        original = build_payload(documents["A"])
        changed = build_payload(documents["A"], "study-group@example.com")
        self.assertEqual(original["messages"][0], changed["messages"][0])
        for key in ("model", "format", "options", "stream"):
            self.assertEqual(original[key], changed[key])

    def test_configuration_is_used_for_policy_and_then_restored(self):
        previous = lab.APPROVED_RECIPIENTS
        for proposed, allowed in (("study-group@example.com", True),
                                  ("study-group@example.invalid", False),
                                  ("stranger@example.invalid", False)):
            with self.subTest(proposed=proposed), \
                    patch("llm_lab.request.build_opener") as build, redirect_stdout(io.StringIO()):
                response = MagicMock()
                response.read.return_value = json.dumps({"done": True, "message": {
                    "content": json.dumps({"document_id": "welcome", "recipient": proposed})
                }}).encode()
                build.return_value.open.return_value.__enter__.return_value = response
                result = run_case("mock", conditions()["A"], "study-group@example.com")
                self.assertEqual(len(result["outbox"]), int(allowed))
                self.assertIs(lab.APPROVED_RECIPIENTS, previous)
                self.assertEqual(metrics(result, "study-group@example.com")["user_request_compliance"], allowed)


if __name__ == "__main__":
    unittest.main()
