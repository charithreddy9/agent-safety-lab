---
title: "When the Total Is Right"
subtitle: "Can small language models write tests for errors in payment reports?"
author: "Sai Charith Reddy Yaredla"
date: "November 18, 2026 · Release candidate 1 for author review"
---

## Abstract

Testing a financial report requires two judgments. A reviewer must choose transactions on which a faulty report will differ from a correct one, then calculate the output that the correct report should produce. We evaluated these judgments using two fictional payment policies, two local language models, and 40 reviewer responses. In the settlement-day task, none of 20 responses satisfied the strict test contract. An exploratory replay recovered five Qwen inputs that exposed the fault, but all five predicted an incorrect breakdown. In the merchant-attribution task, seven of 20 responses supplied scorable inputs. All seven exposed the fault; five also predicted the correct result. These pilots illustrate why evaluations of generated tests should report input quality and expected-output accuracy separately. They provide limited evidence about the effect of showing reviewers the implementation.

## 1. Research question

A $100 sale settles on Monday and a $20 refund settles on Tuesday. A faulty report assigns both events to Monday. The weekly total is $80 in either report. A useful test needs a cross-day refund and an assertion that Tuesday records **−$20**. Generating the right transactions solves only the first part of the problem.

We ask whether reviewers shown a reporting policy can construct such tests, and whether showing the candidate SQL changes their success. Prior work documents the influence of faulty code on LLM-generated tests [1]. TS-SQL generates test data and checks for text-to-SQL [2]. SynSQL constructs databases conditioned on a question and schema [3], while SpotIt+ searches for inputs that distinguish candidate and reference queries [4]. Here the generated test must supply both its input and a complete expected report. A separate implementation computes the answer used for grading.

## 2. Experimental design

We used Qwen3 4B and Llama 3.2 through local Ollama. For each policy and model, each of five seeds produced a matched pair of responses in separate conversations. The visible reviewer received the policy, schema, test instructions and faulty SQL. The hidden reviewer received the same instructions with the SQL omitted. The reference query was withheld from both. Arm order alternated by seed. Each response had a 1,200-token budget, temperature 0.3 and a limit of six input sales. Qwen used thinking disabled in these controlled reviews.

\newpage

## 3. Tasks and scoring

**Settlement day.** A refund reduces the daily report on its settlement date. The faulty query applies it to the original sale date. Across 324 enumerated single-sale and two-sale histories, the period totals always agreed. The daily breakdowns differed in all 189 histories with a later-day refund and agreed in the other 135.

**Merchant attribution.** A sale belongs to its fulfilling merchant. The faulty query credits the booking merchant. Across 44 enumerated histories the grand total always agreed, while 28 merchant breakdowns differed. An input with different booking and fulfilling merchants can still be uninformative if equal transfers cancel.

**Scoring.** For valid input rows, we compare the faulty query's result with the reference breakdown. A test earns full credit if the two reports differ and the proposed expected result matches the entire reference breakdown. Invalid inputs earn zero end-to-end credit. Settlement-day scoring originally required positional arrays. Following inspection of that pilot, the merchant task specified in advance that positional arrays and objects with complete, exact field names were acceptable. The policy and representation rules therefore both changed between tasks.

## 4. Results

| Policy and model | SQL shown: scorable / exposed / detected | SQL hidden: scorable / exposed / detected |
|---|---:|---:|
| Settlement day · Qwen | 0 / 0 / 0 | 0 / 0 / 0 |
| Settlement day · Llama | 0 / 0 / 0 | 0 / 0 / 0 |
| Merchant attribution · Qwen | 4 / 4 / 2 | 2 / 2 / 2 |
| Merchant attribution · Llama | 1 / 1 / 1 | 0 / 0 / 0 |

*Table 1. Each cell covers five attempted tests. The three counts are nested: inputs the scorer accepted, inputs on which the reports differed, and tests that also predicted the complete correct breakdown. All 40 calls recorded a normal stop in Ollama 0.40.16.*

**Settlement day.** All 20 responses failed strict input validation. In an exploratory replay, five hidden-query Qwen replies provided all five required fields as named objects. Converting them to arrays without changing values exposed the fault in every case. All five expectations were wrong. For example, one reply proposed a 100-cent sale followed by a 50-cent refund the next day, then expected +100 and +50. The reference produced +100 and −50. Those five replies contained three distinct test payloads. All five SQL-visible Qwen replies repeated the same three sales and omitted refund fields. All ten Llama replies supplied dates and net amounts without the required sale-to-refund links.

**Merchant attribution.** Seven responses supplied valid inputs, all of which exposed the fault. Qwen supplied four of these with SQL visible and two with SQL hidden. Llama supplied one with SQL visible. Qwen detected the fault in both arms for one seed, only in each respective arm for one seed apiece, and in neither for two. Llama detected it only in the visible arm for one seed.

\newpage

## 5. Why informative inputs still failed

Both scorable merchant tests with wrong expectations came from Qwen's SQL-visible condition. Their proposed breakdowns overstated even the grand total. Sales worth 1,500 cents produced an expectation of 1,700 cents in one case. In the other, sales worth 2,100 cents produced an expectation of 3,101 cents. A total check could have rejected both proposed expectations. The assignment bug itself requires a separate check of the merchant breakdown.

Of the 13 invalid merchant replies, four Qwen replies had malformed IDs or field names, or incomplete rows. Nine Llama replies omitted the required top-level rows key. In an exploratory replay, renaming only the input key in six of these Llama replies allowed all six to be scored. Five then exposed the fault but predicted wrong totals. The sixth predicted the correct output for an input on which both queries agreed. The replay added zero full detections.

## 6. Scope and limitations

The author-pilot summary records ten attempts to generate queries. Eight stopped at the author stage, one timed out, and one completed without a qualifying total-preserving error on the validation fixtures. This left no eligible self-review comparison. The controlled results in Table 1 concern **review of supplied SQL**.

The study uses one planted fault per policy, two local model configurations, and repeated seeds on the same prompts. The enumerated histories are calibration cases, not independent model trials. Repeated payloads further limit generalization. The visible-versus-hidden counts do not establish a preferred reviewer workflow. A replication should hold representation rules constant across policies and test independently selected reporting faults.

## Reproducibility and disclosures

The research branch contains policies, prompts, SQL implementations and scoring code. Replaying both operator-supplied archives matched the saved requests and reproduced all 40 controlled reviewer scores. The replay covers the two supplied-query tasks. The author-pilot counts come from the earlier pilot summary. Diagnostic conversions are reported separately from the original scores. The study used fictional transactions. An AI assistant helped develop the experiments, inspect the outputs and draft this manuscript. The author ran the local model trials. This draft is prepared for author review.

[Research code and run instructions](https://github.com/charithreddy9/agent-safety-lab/tree/research/payment-report-review/research/payment-report-review)

## References

[1] [Evaluating and Mitigating the Misguidance Effect of Buggy Code in LLM-Generated Unit Tests](https://doi.org/10.1145/3832204).  
[2] [TS-SQL: Test-driven Self-refinement for Text-to-SQL](https://aclanthology.org/2025.findings-emnlp.156/).  
[3] [SynSQL: Synthesizing Relational Databases for Robust Evaluation of Text-to-SQL Systems](https://arxiv.org/abs/2604.27261).  
[4] [SpotIt+: Verification-based Text-to-SQL Evaluation with Database Constraints](https://arxiv.org/abs/2603.04334).
