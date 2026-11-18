# When the Total Is Right
## A settlement-day benchmark for studying AI review of payment reports

**Working manuscript · November 17, 2026**

### Abstract

A payment report can reconcile over an entire reporting period while misstating activity on individual days. We introduce a small executable benchmark for testing whether AI reviewers generate examples and expected results that distinguish these reports. As a calibration experiment, we enumerate 324 synthetic histories of one or two sales over three dates and evaluate a deliberately faulty SQLite report against an independent Python calculation. Whole-period totals agree in all 324 histories. Exact daily breakdowns disagree in all 189 histories with a later-day refund and agree in the other 135. This validates the benchmark's ability to separate two kinds of assertions. The comparison between AI review workflows is specified for subsequent measurement.

### Motivation and related work

If a sale of $100 settles on Monday and its $20 refund settles Tuesday, the correct daily amounts are $100 and −$20. Crediting the refund to Monday preserves the $80 period total. This scenario tests two decisions by a reviewer. Can it construct an informative transaction history? Can it predict the correct result at the reporting granularity required by the policy?

Prior work on implementation-induced test bias motivates comparing reviewers with different access to the author's output [1]. TS-SQL generates test data and executable checks for text-to-SQL [2]. SynSQL synthesizes databases from the question and schema [3]. SpotIt+ searches for differentiating instances given candidate and reference SQL [4]. Our development benchmark fixes one reporting policy and separately scores input validity, expected output and detection. The contribution at this stage is the inspectable calibration task and paired protocol.

### Method and calibration

The policy permits one settled sale and zero or one refund per row, in a single currency. Amounts are integers in cents. A sale can be 100 or 200 cents. A refund is a positive multiple of 100 cents up to the sale amount and can occur on the sale date or either remaining eligible date in a three-day window. There are 24 distinct valid single-sale records. Unordered pairs with replacement give 300 additional histories. We assign distinct sale IDs within each history. Each possible history receives equal weight for this enumeration.

The reference query groups positive sales and negative refunds by their respective settlement dates. The planted fault groups both by the sale date. A Python implementation independently accumulates daily net amounts. Both implementations include zero-net days that have activity. We compare unordered day-and-amount pairs, and separately compare whole-period totals.

| Calibration observation | Count |
|---|---:|
| Reference SQL agrees with Python | 324 / 324 |
| Grand-total check exposes the fault | 0 / 324 |
| Daily breakdown exposes the fault | 189 / 324 |
| Daily breakdown exposes the fault given a later-day refund | 189 / 189 |
| Daily breakdown differs without a later-day refund | 0 / 135 |

The result follows from the fault construction. Moving a refund between days leaves its amount unchanged. Consider the earliest sale date of any shifted refund. At that date, the faulty report subtracts money early, and no earlier shifted refund can offset the error there. The bounded enumeration checks that the executable scorer exhibits this behavior. The frequency 189/324 describes this constructed domain only.

### Planned AI comparison

For each model and seed, generate one SQL report. Save it before review. Ask the author session and a fresh session of the same model to generate one test each under identical row and output limits. The first session retains the query and author exchange. The fresh session receives the policy and schema. Score both tests on the same saved query. Report the number of eligible faulty reports, both-detect, author-only, fresh-only and neither, including invalid outputs and incomplete pairs. If no eligible reports occur, report that outcome. A seeded-fault study would answer a separate question about reviewing supplied code.

### Limitations and release decision

One synthetic policy and one planted fault provide a calibration example. Detection frequencies do not estimate operational prevalence. The paired comparison combines query visibility and author context. The present data support no claim about which AI workflow performs better. An independent rerun and a second reporting policy would strengthen a benchmark release. Before submission, the researcher should review the analysis, verify the source references and complete authorship and tool-use disclosures for the chosen venue.

### Reproduction

With Python 3.10 or newer, run `python study.py` followed by `python bounded_audit.py` in this directory. Compare the latter output to `audit-results.json`. The README describes the local-model protocol.

### References

1. [Evaluating and Mitigating the Misguidance Effect of Buggy Code in LLM-Generated Unit Tests](https://doi.org/10.1145/3832204)
2. [TS-SQL: Test-driven Self-refinement for Text-to-SQL](https://aclanthology.org/2025.findings-emnlp.156/)
3. [SynSQL: Synthesizing Relational Databases for Robust Evaluation of Text-to-SQL Systems](https://arxiv.org/abs/2604.27261)
4. [SpotIt+: Verification-based Text-to-SQL Evaluation with Database Constraints](https://arxiv.org/abs/2603.04334)
