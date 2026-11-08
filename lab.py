"""A deterministic, offline experiment. No AI service or email is used."""

import json
from pathlib import Path

DOCUMENTS = Path(__file__).with_name("documents.json")
APPROVED_RECIPIENTS = {"study-group@example.invalid"}


def read_documents():
    """Turn a local JSON file into Python dictionaries."""
    return json.loads(DOCUMENTS.read_text(encoding="utf-8-sig"))


def simulate_share(document, recipient, outbox):
    """Check trusted policy before adding a message to an in-memory list."""
    if document.get("classification") != "public":
        return "BLOCKED: only public documents may be shared"
    if recipient not in APPROVED_RECIPIENTS:
        return "BLOCKED: recipient is not approved"
    outbox.append({"document_id": document["id"], "recipient": recipient,
                   "body": document["text"]})
    return "ALLOWED: added to simulated outbox"


def execute_proposal(proposal, document_store, outbox):
    """Resolve an untrusted proposal against trusted documents, then check policy."""
    if not isinstance(proposal, dict) or set(proposal) != {"document_id", "recipient"}:
        return "BLOCKED: proposal must contain only document_id and recipient"
    if not all(isinstance(value, str) for value in proposal.values()):
        return "BLOCKED: proposal values must be strings"
    document = document_store.get(proposal["document_id"])
    if document is None:
        return "BLOCKED: unknown document ID"
    return simulate_share(document, proposal["recipient"], outbox)


def demonstrate_proposals(document_store):
    """Manually scripted examples; no model generates these actions."""
    proposals = [
        ("Permitted scripted proposal", {
            "document_id": "welcome", "recipient": "study-group@example.invalid"
        }),
        ("Unauthorized scripted proposal", {
            "document_id": "private-notes", "recipient": "stranger@example.invalid"
        }),
    ]
    outbox = []
    print("\nSCRIPTED ACTION PROPOSALS: not model-generated or evidence of LLM security.")
    for label, proposal in proposals:
        print(f"\n{label}")
        print(json.dumps(proposal, indent=2))
        before = len(outbox)
        result = execute_proposal(proposal, document_store, outbox)
        print(f"Trusted classification: {document_store[proposal['document_id']]['classification']}")
        print(f"Decision and reason: {result}")
        print(f"Outbox entries added: {len(outbox) - before}")
        if result.startswith("BLOCKED"):
            assert len(outbox) == before, "Blocked proposal changed the outbox"
            print("Confirmed: blocked proposal added nothing to the outbox.")
    print(f"Scripted-proposal outbox contains {len(outbox)} message(s).")
    print(json.dumps(outbox, indent=2))


def main():
    outbox = []
    print("OFFLINE SIMULATION: nothing is sent.\n")
    documents = read_documents()
    for document in documents:
        print(f"Reading: {document['id']} ({document['classification']})")
        # Reading text does not execute it or turn it into trusted instructions.
        print(f"Document text: {document['text']}")
        for recipient in ("study-group@example.invalid", "stranger@example.invalid"):
            before = len(outbox)
            result = simulate_share(document, recipient, outbox)
            decision, reason = result.split(": ", 1)
            added = len(outbox) - before
            print(f"Classification: {document['classification']}")
            print(f"Recipient: {recipient}")
            print(f"Decision: {decision}")
            print(f"Reason: {reason}")
            print(f"Outbox entries added: {added}")
            if decision == "BLOCKED":
                assert added == 0, "Blocked attempt changed the outbox"
                print("Confirmed: blocked attempt added nothing to the outbox.")
            print()
    print(f"Simulated outbox contains {len(outbox)} message(s).")
    print(json.dumps(outbox, indent=2))
    # The store comes from our local fixtures, never from a proposal.
    document_store = {document["id"]: document for document in documents}
    demonstrate_proposals(document_store)


if __name__ == "__main__":
    main()
