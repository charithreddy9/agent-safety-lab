# Agent instruction conflict pilot

Can a coding model change its decision when existing code and repository guidance
disagree, but the release record changes? Every prompt asks for `POST /exports`.
The existing `POST /reports` returns 200 and the guide recommends 202. Only the
release record changes.

| Scenario | Expected decision | Expected API outcome |
| --- | --- | --- |
| Stale guide | Use 200 | Exports returns 200 |
| Approved migration | Use 202 | Exports returns 202 |
| Unresolved conflict | Ask for clarification | Exports remains absent |

The runner applies the model's structured endpoint proposal to a fresh in-memory
WSGI API and checks the actual response. It records decision correctness, endpoint
correctness, whether the existing endpoint still behaves the same, whether the
model picked the release record, and whether it supplied a question. The runner
only permits edits to the new endpoint, so preserving the existing endpoint
verifies the harness rather than demonstrating model restraint. Question presence
does not establish that a question is useful. Expected answers remain outside the
model prompts.

## Run on your laptop

Requires Python 3.10+ with no Python packages to install. From this directory:

```powershell
python -B -m unittest -v
python -B pilot.py
```

The second command previews the requests and makes zero model calls. With Ollama
running and `llama3.2` installed:

```powershell
python -B pilot.py --run
```

The runner makes one independent localhost request per case, sequentially in
the displayed order, with no retry or fallback. It writes requests, raw
responses when available, scores, and errors to a new `results-*.jsonl` file.
To try another installed model, pass `--model qwen3:4b`.

## Scope

This is a three-case synthetic pilot, informed by the October 2026 preprint
[Stale Instruction Files Override the Code in Coding Agents](https://arxiv.org/abs/2610.30571).
The release records give explicit evidence by design. This pilot measures
structured decisions and endpoint proposals, not autonomous repository editing.
Fixture and mocked transport tests verify the evaluator. Live model results
must come from actual Ollama runs.
