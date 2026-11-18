# When the Total Is Right
## Testing AI review of payment reports with settlement-day and merchant-attribution errors

**Working manuscript · November 18, 2026**

### Abstract

A payment report can reconcile over an entire reporting period while misstating activity on individual days. We introduce a small executable benchmark for testing whether AI reviewers generate examples and expected results that distinguish these reports. As a calibration experiment, we enumerate 324 synthetic histories of one or two sales over three dates and evaluate a deliberately faulty SQLite report against an independent Python calculation. Whole-period totals agree in all 324 histories. Exact daily breakdowns disagree in all 189 histories with a later-day refund and agree in the other 135. This validates the benchmark's ability to separate two kinds of assertions. In ten local model attempts, eight stopped at the author stage, one timed out and one completed without a qualifying error on the validation fixtures. The pilot yielded zero eligible self-review comparisons. In a separate controlled experiment using supplied faulty SQL, the scorer marked all 20 reviewer responses invalid across ten visible/hidden pairs. No pair produced a credited detection.

On a second policy governing merchant attribution, seven of 20 generated inputs exposed the fault and five of those seven responses supplied the correct expected report. The paired results showed no consistent advantage for query visibility across the two models.

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

### AI comparison protocol

For each model and seed, generate one SQL report. Save it before review. Ask the author session and a fresh session of the same model to generate one test each under identical row and output limits. The first session retains the query and author exchange. The fresh session receives the policy and schema. Score both tests on the same saved query. Report the number of eligible faulty reports, both-detect, author-only, fresh-only and neither, including invalid outputs and incomplete pairs. If no eligible reports occur, report that outcome. A seeded-fault study would answer a separate question about reviewing supplied code.

### First local pilot

The operator supplied the run summary and per-seed error messages from the saved logs. The operator also extracted stop reasons, generated-token counts and final-response lengths for Qwen seeds 1–4. Qwen3 4B seeds 1–4 failed JSON decoding at the first character. Seed 5 was interrupted by a timeout. Llama 3.2 seed 2 produced an SQLite incomplete-input error, seed 3 failed report-output validation, and seeds 4–5 referenced an unresolved column named `day`. Llama seed 1 reached both reviews. None of its four fixtures exposed a wrong breakdown with a preserved total. That summary category also admits other kinds of report errors.

The denominator for comparing reviewer detection was zero. For each of Qwen seeds 1–4, Ollama reported a length stop at exactly 1,200 generated tokens and zero characters in the final answer. The parser therefore received an empty string in all four cases. These metadata do not establish how the generated tokens were allocated. In a separate author-only follow-up, the operator set `think=false` with the same prompt, token cap and four seeds. All four replies had nonempty final content. Seeds 1 and 3 stopped normally and returned a nonempty SQL field (525 and 367 response characters). Seed 2 hit the length cap at 4,609 characters and seed 4 stopped normally at 758 characters. Neither yielded a nonempty SQL string under the specified parser. Across these four selected seeds, SQL-field yield was 0/4 in the original run and 2/4 in the follow-up. Offline scoring of the four saved replies produced zero executable reports. Seed 1 referenced an unresolved column (`events.event_day`). Seed 3 referenced a table (`refunds`) absent from the supplied schema, which stores refunds on `sales` rows. Each query failed on all four fixtures and all 324 bounded histories. Seed 2 ended with an unterminated JSON string after reaching the output limit. Seed 4 returned a JSON object containing only `description` and `title`. Thus two replies provided a SQL string, zero produced a daily breakdown, and none qualified for a reviewer comparison. The 324 histories exercise each saved query and do not constitute independent model generations.

### Controlled review of supplied SQL

The operator reported five paired seeds per model for Qwen3 4B and Llama 3.2. Each fresh reviewer received the policy, schema and test request. The visible arm also received the same faulty query. Arm order alternated by seed. No arm received the correct query. The runner evaluated returned tests against both implementations and the independent daily calculation.

| Model | Invalid with query visible | Invalid with query hidden | Pairs with a credited detection |
|---|---:|---:|---:|
| Qwen3 4B | 5/5 | 5/5 | 0/5 |
| Llama 3.2 | 5/5 | 5/5 | 0/5 |

All ten pairs completed. Invalid responses count as failures on the end-to-end detection metric, giving 0/10 detections in each arm. No test reached the scored stage, so detection among scorable tests is undefined. The operator grouped the first recorded exception for each reply. In 10 replies the scorer encountered a sales row that unpacked into two items, and in five it encountered a row that unpacked into three. Each row requires five values. The other five replies reached the sale ID and sale-date checks and raised the shared invalid-sale error. These counts identify the first validation failure per reply. Replaying all 20 archived responses reproduced every recorded scorer result. All five invalid-sale exceptions came from Qwen's hidden-query replies. They supplied five-field objects. Python unpacked their keys, so the ID check received a field name. The strict protocol required arrays. No expected daily breakdown reached comparison with the reference.

### Exploratory inspection of rejected tests

For a secondary analysis, we converted complete named fields to positional arrays without filling missing values or correcting amounts. All five Qwen hidden-query replies contained complete sale and refund data. On each proposed history, executing the correct and faulty queries yielded different daily breakdowns. All five expected breakdowns nevertheless disagreed with the reference. For seed 1, a 100-cent sale followed by a 50-cent refund the next day should yield +100 and −50 cents. The reply predicted +100 and +50. Across seeds there were three distinct hidden-query test payloads.

All five Qwen visible-query replies returned the same three sales and omitted both refund fields. No later-day refund was specified. All ten Llama replies supplied dates and net amounts as inputs, omitting the sale-to-refund relationship needed to load the sales table. Six of these also omitted the expected output. The secondary analysis identified informative inputs in one condition, but yielded zero complete tests that both accept the reference and expose the fault. The repeated payloads and single policy limit generalization.

### Merchant attribution

The correct report credits the fulfilling merchant. The supplied query credits the booking merchant. The scorer accepts positional arrays and complete named objects and scores input discrimination independently of expected-output accuracy. Each model generated one response per condition for each of five paired seeds. The 44-history calibration preserved the grand total throughout and exposed the incorrect breakdown in 28 histories.

| Model | SQL shown | Attempts | Valid inputs | Inputs exposing fault | Correct expected output | Full detections |
|---|---|---:|---:|---:|---:|---:|
| Qwen3 4B | Yes | 5 | 4 | 4 | 2 | 2 |
| Qwen3 4B | No | 5 | 2 | 2 | 2 | 2 |
| Llama 3.2 | Yes | 5 | 1 | 1 | 1 | 1 |
| Llama 3.2 | No | 5 | 0 | 0 | 0 | 0 |

The operator supplied aggregate output for this experiment. The paired counts agree with the arm totals. For Qwen, one seed succeeded in both conditions, one only with the query visible, one only with it hidden and two in neither. Llama succeeded only in the visible condition for one seed and in neither for four. Across 20 responses, 13 failed input validation. All seven scorable inputs distinguished the reports. Two of these seven lacked a matching expected result, both from Qwen with the query visible. The aggregate counts do not identify why those expectations failed. Raw merchant records await replay.

### Limitations and release decision

Each of two synthetic policies has a single planted fault. The merchant experiment also changed the accepted input representations, limiting direct comparison of success rates between tasks. Detection frequencies do not estimate operational prevalence. The original self-review protocol combines query visibility and author context, while the supplied-query experiments use fresh review sessions. The present data support no claim about which AI workflow performs better. An independent rerun and tests on additional policies and faults would strengthen a benchmark release. Before submission, the researcher should review the analysis, verify the source references and complete authorship and tool-use disclosures for the chosen venue.

### Reproduction

With Python 3.10 or newer, run `python study.py` followed by `python bounded_audit.py` in this directory. Compare the latter output to `audit-results.json`. The README describes the local-model protocol.

### References

1. [Evaluating and Mitigating the Misguidance Effect of Buggy Code in LLM-Generated Unit Tests](https://doi.org/10.1145/3832204)
2. [TS-SQL: Test-driven Self-refinement for Text-to-SQL](https://aclanthology.org/2025.findings-emnlp.156/)
3. [SynSQL: Synthesizing Relational Databases for Robust Evaluation of Text-to-SQL Systems](https://arxiv.org/abs/2604.27261)
4. [SpotIt+: Verification-based Text-to-SQL Evaluation with Database Constraints](https://arxiv.org/abs/2603.04334)
