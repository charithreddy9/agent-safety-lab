# When the Total Is Right
## Release candidate for author review · November 18, 2026

Read [the release candidate](preprint.md) for the findings on review of supplied SQL. The [working manuscript](manuscript.md) preserves the development history, including the earlier self-review pilot, which yielded no eligible comparison.

### Reproduce the controlled results

From this directory, run the following with Python 3.10+ and the two original trial archives. The command reads the ZIPs directly and requires no model service. Supply paths to the ZIP files if stored elsewhere.

    python replay_controlled.py reviewer-trials.zip merchant-reviewer-trials.zip

Compare the output with [controlled-results.json](controlled-results.json). It records SHA-256 hashes of both archives, model digests, Ollama versions, completion reasons, per-arm counts and matched-pair outcomes. The script checks each saved request against the protocol and recalculates every score from its original response. The branch includes the aggregate replay output. The original ZIPs are held separately.

### Original self-review protocol · November 17, 2026

A reporting query can reconcile to the cent over a week while moving a refund from Tuesday to Monday. The original pilot asked whether a model reviewing its own saved SQL or a fresh instance of the same model would design a test that exposes such an error.

### Paper premise

Earlier work demonstrates that buggy implementation context can mislead LLM test writers. TS-SQL generates test data and assertions for SQL, and SynSQL generates databases from a question and schema. Our proposed contribution is a paired evaluation of errors that preserve aggregate value while changing the distribution across reporting groups. Its novelty and importance remain hypotheses. A one-rule feasibility run supports protocol development only.

- [Misguidance effect in LLM-generated unit tests](https://doi.org/10.1145/3832204)
- [TS-SQL, Findings of EMNLP 2025](https://aclanthology.org/2025.findings-emnlp.156/)
- [SynSQL, 2026 preprint](https://arxiv.org/abs/2604.27261)
- [SpotIt+, 2026 preprint](https://arxiv.org/abs/2603.04334)

### Protocol

1. Generate a report once per model and seed. Save the raw reply. Both reviewers evaluate that exact query. Self-review retains the author prompt and answer. Independent review receives the same policy, schema, test request, model, seed, temperature and output budget in a fresh conversation. The contrast measures the combined effect of author history and query visibility. A later fresh reviewer who sees the SQL would isolate those effects.
2. Use four hidden fixtures to characterize the author output. Record generation errors, valid queries passing all fixtures, and queries with at least one incorrect breakdown whose total balances. Passing four fixtures establishes only observed agreement. Inspect queries with mixed failure types before attributing the error specifically to refund dating.
3. Each reviewer proposes one test with up to six sales and a complete expected daily breakdown. A separate Python calculation checks the lifecycle and expected output in integer cents. Duplicate dates in the report output, missing zero-net days and incorrect amounts count as differences. An invalid test receives no detection credit. Execution or format failures are logged separately where possible.
4. The primary descriptive result is the paired detection count on reports with a balanced error on the hidden fixtures. Score only tests with valid input, exact expected output, a disagreement with the saved report and an unchanged grand total. Report both-detect, self-only, independent-only and neither, plus the number of eligible reports out of all author attempts. Also inspect how often rows discriminate but expectations are wrong. Separately record newly exposed errors on queries that passed the fixtures.
5. Start with seeds 1–5 on each available model. Record the Ollama version, exact model digest, hardware and date alongside the JSONL files. Keep every attempted run including malformed replies. Report interruptions as missing pairs. If no eligible errors occur, the natural-error comparison is uninformative. Evaluate seeded faults separately, under the label “review of supplied SQL.” Never count a hand-written query as an agent's own mistake.
6. Before a larger study, freeze prompts and scoring on this development rule. Add held-out policies for merchant attribution and account allocation, an independent check of policy labels, a valid-random baseline and a boundary-case baseline. Report per-rule results. Repeated seeds on the same policy are not independent evidence of generalization.

### Running the pilot on Windows

Extract the folder and open PowerShell there. Python 3.10+ suffices for the fixture check.

    py study.py

For a live trial, start Ollama with the chosen model installed, then run:

    py study.py --model qwen3:4b --seed 1 --out qwen-seed1.jsonl

Use a new output filename for each trial. The runner refuses to overwrite previous trials. Each completed trial makes three local inference calls. Keep raw outputs for later audit. An unavailable model service may leave a partial log. Use a new filename for a retry and record why.

### Verified fixture results

| Synthetic scenario | Reference daily report | Wrong refund date exposed? |
|---|---|---|
| $100 Monday, $20 refunded Tuesday | Monday $100, Tuesday −$20 | Yes |
| $100 Monday, $20 refunded Monday | Monday $80 | No |
| $100 Monday, no refund | Monday $100 | No |
| $100 Monday fully refunded Tuesday, another $100 sale Tuesday | Monday $100, Tuesday $0 | Yes |

The SQLite reference agreed with the independently calculated breakdown on all four fixtures. The seeded fault preserved the total and changed the breakdown on two. A test that expected the faulty Monday-only answer was rejected. These four fixtures validate the scorer. Table 1 in the release candidate reports the subsequent supplied-query trials.

### Manuscript structure

**Introduction.** Motivate the question with the two-day refund. **Related work.** Position the experiment against SQL testing and implementation-induced test bias. **Methods.** Publish policies, prompts, budgets, eligibility and paired scoring. **Results.** Fill in author error prevalence, paired detection counts, invalid tests and representative missed breakdowns after inference. **Limitations.** Address synthetic data, limited model families, dependence across seeds, code visibility and error scarcity. **Discussion.** Identify which review workflows the observations support and specify where replication is needed.

### Merchant-attribution replication

Run `python review_merchant.py` from this directory with the two pilot models installed in Ollama. This prospective extension uses one supplied fault that assigns sales to the booking merchant instead of the fulfilling merchant. Both arms use the same field names and accept positional arrays or complete named objects, without imputing missing values. Within each model, compare query-visible and query-hidden tests at seeds 1–5. An input distinguishes the reports if the two executable queries disagree. Independently evaluate the submitted expected breakdown against the fulfilling-merchant reference. Full detection requires both conditions. Inputs without a usable expectation can still earn input credit. Report missing requests separately. The change of policy and accepted representations limits direct comparisons with the original strict refund pilot. The 44-history calibration includes offsetting transfers that leave even merchant totals unchanged. Live responses are saved in `merchant-review-trials`.
