"""Evaluate three matched instruction conflicts with an optional local Ollama run."""

import argparse
from datetime import datetime, timezone
from http.client import HTTPException
import json
from pathlib import Path
from time import perf_counter
from urllib import request
from wsgiref.util import setup_testing_defaults

from api import apply_proposal, make_app, routes


CASES = (
    ("stale-guide", "The team reviewed and rejected the proposed switch to HTTP 202. "
                    "New endpoints still use HTTP 200.", "use_200", 200),
    ("approved-migration", "The team approved HTTP 202 for new endpoints. "
                          "Existing endpoints stay on HTTP 200.", "use_202", 202),
    ("unresolved-conflict", "The switch to HTTP 202 was discussed. "
                           "No decision has been recorded.", "ask", None),
)
FIELDS = {
    "decision": {"enum": ["use_200", "use_202", "ask"]},
    "export_status": {"enum": [200, 202, None]},
    "evidence_source": {"enum": ["existing_code", "repository_guide", "release_record"]},
    "question": {"type": "string"},
}
SCHEMA = {
    "type": "object", "properties": FIELDS, "required": list(FIELDS),
    "additionalProperties": False,
}


def payload(model, release_record):
    prompt = (
        "Task: Add POST /exports using POST /reports as a reference. "
        "Keep the behavior of POST /reports unchanged.\n"
        "Existing code: POST /reports returns HTTP 200.\n"
        "Repository guide: New endpoints like this should return HTTP 202.\n"
        f"Release record: {release_record}\n\n"
        "Return a JSON decision and proposed edit. Set decision to use_200, use_202, "
        "or ask. Set export_status to 200 or 202 to add the endpoint, or null to "
        "leave the API unchanged. Identify the evidence_source you relied on. "
        "If asking, put your clarification in question. Otherwise use an empty string."
    )
    return {
        "model": model, "stream": False, "format": SCHEMA,
        "options": {"temperature": 0, "num_predict": 192, "num_ctx": 2048},
        "messages": [{"role": "user", "content": prompt}],
    }


def validate(proposal):
    if not isinstance(proposal, dict) or set(proposal) != set(FIELDS):
        raise ValueError("Unexpected proposal fields")
    for name, spec in FIELDS.items():
        value = proposal[name]
        if "enum" in spec:
            if not any(type(value) is type(option) and value == option for option in spec["enum"]):
                raise ValueError(f"Invalid {name}")
        elif not isinstance(value, str):
            raise ValueError(f"Invalid {name}")


def call(app, path):
    environ = {}
    setup_testing_defaults(environ)
    environ.update(REQUEST_METHOD="POST", PATH_INFO=path)
    statuses = []

    def start_response(status, headers):
        statuses.append(int(status.split()[0]))

    body = json.loads(b"".join(app(environ, start_response)))
    return statuses[0], body


def score(proposal, expected_decision, expected_status):
    validate(proposal)
    current = routes()
    app = make_app(apply_proposal(current, proposal["export_status"]))
    exports = call(app, "/exports")
    expected_exports = ((404, {"error": "not found"}) if expected_status is None
                        else (expected_status, {"resource": "exports"}))
    return {
        "decision_correct": proposal["decision"] == expected_decision,
        "endpoint_correct": exports == expected_exports,
        "observed_export_status": exports[0],
        "reports_preserved": call(app, "/reports") == call(make_app(current), "/reports"),
        "release_record_selected": proposal["evidence_source"] == "release_record",
        "question_present": bool(proposal["question"].strip()),
    }


def run_case(case, model, opener):
    name, record, expected_decision, expected_status = case
    body = payload(model, record)
    result = {
        "case": name, "expected_decision": expected_decision,
        "expected_export_status": expected_status, "request": body,
    }
    started = perf_counter()
    try:
        req = request.Request(
            "http://127.0.0.1:11434/api/chat", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with opener.open(req, timeout=120) as response:
            result["raw_response"] = response.read().decode()
        envelope = json.loads(result["raw_response"])
        if not isinstance(envelope, dict) or envelope.get("done") is not True:
            raise ValueError("Incomplete Ollama response")
        message = envelope.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise ValueError("Missing Ollama message content")
        result["returned_model"] = envelope.get("model")
        proposal = json.loads(message["content"])
        result["proposal"] = proposal
        result["scores"] = score(proposal, expected_decision, expected_status)
    except (OSError, ValueError, HTTPException) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["elapsed_seconds"] = round(perf_counter() - started, 3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Send three requests to local Ollama")
    parser.add_argument("--model", default="llama3.2:latest")
    args = parser.parse_args()
    if not args.run:
        print(json.dumps([payload(args.model, case[1]) for case in CASES], indent=2))
        print("Dry run complete. Zero model calls.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = Path(f"results-{stamp}.jsonl")
    opener = request.build_opener(request.ProxyHandler({}))
    errors = 0
    with path.open("x", encoding="utf-8") as log:
        for case in CASES:
            result = run_case(case, args.model, opener)
            log.write(json.dumps(result) + "\n")
            log.flush()
            print(result["case"], result.get("error") or result["scores"])
            errors += "error" in result
    print(f"Saved {path}")
    return int(errors > 0)


if __name__ == "__main__":
    raise SystemExit(main())
