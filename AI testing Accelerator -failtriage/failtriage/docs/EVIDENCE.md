# Evidence that it helps

## What "better" means here

Triage has three jobs, so there are three things to measure.

| Question | Metric |
|---|---|
| Is it faster? | Wall-clock time to triage a full run. Number of items a human must look at. |
| Is it right? | Per-test category accuracy and macro-F1 against human labels. Per-category precision/recall. Confusion matrix. |
| Is it safe to rely on? | **Silent errors**: wrong verdicts the tool did *not* flag for review. Accuracy of confident vs flagged verdicts. |

Silent errors matter most in a bank. A wrong answer that is flagged costs a minute of human time. A wrong answer delivered with confidence is how a real defect gets dismissed as "flaky".

## Method

1. **Labelled run.** `data/eval_run/` holds 71 failing tests from one simulated nightly run. They span four report formats and **32 root causes**, each labelled with a category and a one-line justification in `labels.csv`.
   - The mix is deliberately environment-heavy (29 of 71), which matches what shared SIT environments produce.
   - It includes the cases that trip people and rules up:
     - a Kafka outage that only shows as a timeout
     - an expired OAuth secret (401)
     - intermittent 503s with a flipping history
     - a performance regression that surfaces as a UI timeout
     - assertions broken by *intentional* changes listed in `context.json`
2. **Three ways of working, same input.**
   - **Manual:** an engineer triages with the XML reports, logs and history, and is timed (protocol below).
   - **Rules baseline:** the keyword tagger many teams already have (`--engine rules`).
   - **Claude:** `failtriage` with masking, grouping and the LLM.
3. **Scoring.** `python -m failtriage eval data/eval_run` scores every engine with the same code (`failtriage/evaluate.py`). Each failing test inherits the verdict of the group it was placed in.

### Manual timing protocol

1. Copy `results/manual_timing_template.csv` to `results/manual_timing.csv`.
2. Triage a random sample of about 20 tests using only the reports, logs, history and context. Do not look at `labels.csv`.
3. Record seconds and your category per test.

The next `eval` run adds a *Manual* column. Time is extrapolated to all 71 tests, and your accuracy is scored against the labels.

## Results

Numbers below come from `results/EVAL_RESULTS.md`.
The **rules baseline** column is from an actual run of this repo.
The **Claude** and **Manual** columns must come from your own run (step 4 of the README, plus the timing protocol). Paste them in. Do not estimate them.

| Metric | Manual (timed) | Rules baseline | Claude (`claude-sonnet-5-5`) |
|---|---|---|---|
| Time to triage the whole run | _fill_ | < 1 s | _fill_ |
| Issues a human must look at | 71 (one per failure) | 34 (true: 32) | _fill_ |
| Category accuracy (per test) | _fill_ | **80%** | _fill_ |
| Macro-F1 | – | 0.79 | _fill_ |
| Grouping pairwise F1 | – | 0.99 (same grouper) | 0.99 (same grouper) |
| Wrong **and not flagged** (silent errors) | – | **12 of 71** | _fill_ |
| Tokens in / out (cost) | – | 0 | _fill_ |

**Where the rules baseline fails.** It makes 14 errors, 12 of them silent:
- the expired OAuth secret (401 → called product bug, 3 tests)
- the Kafka outage and the intermittent card-gateway 503s (called flaky, 4 tests)
- the intentional currency-format and JSON-path changes (called product bug, 4 tests)
- a test-order dependency (called product bug)
- the performance regression (called flaky, 2 tests)

These are exactly the cases where the decisive evidence is in the log lines, the history or the change list rather than the exception type. That is the gap the LLM is meant to close.

### How to read the result

- **Accuracy** should beat the rules baseline on the hard cases above. The interesting rows are in the misclassification table of `EVAL_RESULTS.md`.
- **Silent errors** should be near zero. If the model is wrong, it should usually be below the review threshold.
- **Time:** the manual column is minutes per test × 71. The tool column is seconds, plus human review of the groups it shows.
  So the honest saving is **(manual minutes) − (tool runtime + review of ~30 groups and the flagged ones)**. Report both numbers, not just the tool runtime.

## Threats to validity (said up front)

- **Synthetic data.** The labelled run is synthetic. It is modelled on real failure patterns, but it was written by the same person who wrote the rules and labels. That biases the result in two directions: the hard cases were chosen knowing what rules miss.
  The next step is to re-run on 2–3 *real*, anonymised past runs whose root causes are already known from Jira. `parse_run` takes any folder of reports; add a `labels.csv`.
- **Small sample.** With n = 71 and 32 root causes, one group flipping moves accuracy by several points. Report the confusion matrix, not just one number.
- **Labelling.** Some labels are judgement calls, e.g. intermittent 503s are ENVIRONMENT, not FLAKY. A second labeller and an agreement score would strengthen this.
- **Model drift.** Results are tied to the model version and the prompt version (`triage-v1.2`), both of which are recorded in every audit line. Re-run `eval` whenever either changes. Treat it as a regression suite for the triager itself.
