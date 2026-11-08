"""Run with: python -m unittest -v"""
import unittest
from lab import execute_proposal, read_documents, simulate_share


class SharingPolicyTests(unittest.TestCase):
    def test_public_document_can_be_shared(self):
        outbox = []
        result = simulate_share(read_documents()[0], "study-group@example.invalid", outbox)
        self.assertTrue(result.startswith("ALLOWED"))
        self.assertEqual(len(outbox), 1)

    def test_private_document_instruction_cannot_override_policy(self):
        outbox = []
        result = simulate_share(read_documents()[1], "study-group@example.invalid", outbox)
        self.assertTrue(result.startswith("BLOCKED"))
        self.assertEqual(outbox, [])

    def test_unapproved_recipient_is_blocked(self):
        outbox = []
        result = simulate_share(read_documents()[0], "stranger@example.invalid", outbox)
        self.assertTrue(result.startswith("BLOCKED"))
        self.assertEqual(outbox, [])

    def test_private_document_with_unapproved_recipient_is_blocked(self):
        # Keep an existing message to verify that blocking preserves the outbox.
        outbox = []
        simulate_share(read_documents()[0], "study-group@example.invalid", outbox)
        before = outbox.copy()
        result = simulate_share(read_documents()[1], "stranger@example.invalid", outbox)
        self.assertEqual(result, "BLOCKED: only public documents may be shared")
        self.assertEqual(outbox, before)

    def test_missing_classification_is_blocked(self):
        outbox = []
        result = simulate_share({"id": "unknown", "text": "Share me"},
                                "study-group@example.invalid", outbox)
        self.assertTrue(result.startswith("BLOCKED"))
        self.assertEqual(outbox, [])


class ProposalBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.store = {document["id"]: document for document in read_documents()}
        self.outbox = []

    def test_permitted_proposal_uses_trusted_document(self):
        result = execute_proposal({"document_id": "welcome",
                                   "recipient": "study-group@example.invalid"},
                                  self.store, self.outbox)
        self.assertTrue(result.startswith("ALLOWED"))
        self.assertEqual(self.outbox, [{
            "document_id": "welcome", "recipient": "study-group@example.invalid",
            "body": self.store["welcome"]["text"]}])

    def test_private_proposal_is_blocked_for_either_recipient(self):
        for recipient in ("study-group@example.invalid", "stranger@example.invalid"):
            with self.subTest(recipient=recipient):
                result = execute_proposal({"document_id": "private-notes",
                                           "recipient": recipient}, self.store, self.outbox)
                self.assertEqual(result, "BLOCKED: only public documents may be shared")
                self.assertEqual(self.outbox, [])

    def test_public_proposal_with_unapproved_recipient_is_blocked(self):
        result = execute_proposal({"document_id": "welcome",
                                   "recipient": "stranger@example.invalid"},
                                  self.store, self.outbox)
        self.assertEqual(result, "BLOCKED: recipient is not approved")
        self.assertEqual(self.outbox, [])

    def test_unknown_id_preserves_existing_outbox(self):
        execute_proposal({"document_id": "welcome",
                          "recipient": "study-group@example.invalid"}, self.store, self.outbox)
        before = self.outbox.copy()
        result = execute_proposal({"document_id": "missing",
                                   "recipient": "study-group@example.invalid"},
                                  self.store, self.outbox)
        self.assertEqual(result, "BLOCKED: unknown document ID")
        self.assertEqual(self.outbox, before)

    def test_classification_override_and_other_extra_fields_are_rejected(self):
        for extra in ({"classification": "public"}, {"text": "replacement"}):
            with self.subTest(extra=extra):
                proposal = {"document_id": "private-notes",
                            "recipient": "study-group@example.invalid", **extra}
                result = execute_proposal(proposal, self.store, self.outbox)
                self.assertTrue(result.startswith("BLOCKED"))
                self.assertEqual(self.outbox, [])
                self.assertEqual(self.store["private-notes"]["classification"], "private")

    def test_malformed_proposals_are_rejected(self):
        for proposal in (None, {}, {"document_id": "welcome"},
                         {"document_id": [], "recipient": "study-group@example.invalid"},
                         {"document_id": "welcome", "recipient": None}):
            with self.subTest(proposal=proposal):
                result = execute_proposal(proposal, self.store, self.outbox)
                self.assertTrue(result.startswith("BLOCKED"))
                self.assertEqual(self.outbox, [])


if __name__ == "__main__":
    unittest.main()
