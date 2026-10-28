# failtriage — AI triage for failing regression runs
GitHub Link- https://github.com/NamanTheCoder/AI-Testing-Accelator


**Turns a red nightly run into a short, ranked list of root causes with draft Jira tickets.**
Each one is classified as a product bug, a test bug, an environment issue, or a flaky test.
Sensitive data is masked before anything is sent to the model, and every decision is audit-logged.

```
JUnit / TestNG / PyTest XML ──► parse ──► mask PII ──► group by root cause ──► Claude classifies each group
                                                                                   │
                     triage_report.md ◄── draft tickets ◄── audit.jsonl ◄──────────┘
```

| Document | What it covers |
|---|---|
| [docs/PROBLEM_STATEMENT.md](docs/PROBLEM_STATEMENT.md) | The problem, who has it, how it is handled today |
| [docs/EVIDENCE.md](docs/EVIDENCE.md) | How it was measured, with the results table |
| [docs/LIMITS_AND_RISKS.md](docs/LIMITS_AND_RISKS.md) | Where it is wrong, what humans must check, what to change for a bank |

---

## Run it in under 10 minutes

You need Python 3.10+ and either:
- An **Anthropic API key** ([console.anthropic.com](https://console.anthropic.com)), OR
- A **GROQ API key** ([console.groq.com](https://console.groq.com)) for free model access

No key? Every command also works offline with `--engine rules`.

**1. Install (about 1 minute)**

```bash
git clone <this-repo-url> failtriage && cd failtriage
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**2. Set your API key**

**Option A: Using Anthropic Claude (Recommended for production)**
```bash
export ANTHROPIC_API_KEY=sk-ant-...  # Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
```

**Option B: Using GROQ (Free models, great for testing)**
```bash
export GROQ_API_KEY=gsk_...  # Windows PowerShell: $env:GROQ_API_KEY="gsk_..."
```

**3. Triage the sample nightly run (36 failures, about 1 minute)**

```bash
python -m failtriage run samples/nightly_run --out out
```

Open `out/triage_report.md`, then a ticket in `out/tickets/`.

**4. Reproduce the evaluation (71 labelled failures, about 2–3 minutes)**

```bash
python -m failtriage eval data/eval_run --out results
```

This runs the rules baseline and Claude against the same labelled run, then writes `results/EVAL_RESULTS.md`.

**5. Run the tests (no API calls)**

```bash
python -m pytest -q
```

**Optional Configuration:**
- Set `TRIAGE_MODEL` to use a different model:
  - For Anthropic: `claude-opus-5-5`, `claude-sonnet-5-5` (default), `claude-haiku-5-5`
  - For GROQ: `mixtral-8x7b-32768`, `llama-3.1-70b-versatile` (default), `llama-3.1-8b-instant`
- `TRIAGE_REVIEW_THRESHOLD` (default `0.70`) sets the confidence below which a verdict is flagged for human review
- Set `LLM_PROVIDER` to `groq` or `anthropic` (auto-detected from API keys)

---

## Sample input and output

**Input:** `samples/nightly_run/`, a realistic nightly run of a banking platform. It contains:
- Surefire/Rest Assured API reports
- a TestNG Selenium UI report
- a PyTest report
- `history.json`: each test's last 10 results
- `context.json`: build and recent intentional changes

The logs deliberately contain fake card numbers, account numbers, customer names, emails and DB passwords to exercise the masking.

**Output (`out/`):**

| File | What it is |
|---|---|
| `triage_report.md` | Run summary: N failures → M issues, ranked by blast radius, review flags |
| `tickets/NN_<CATEGORY>_<group>.md` | Draft Jira ticket per issue, marked **DRAFT — human must review** |
| `triage_result.json` | Machine-readable result, e.g. for a CI step or dashboard |
| `audit.jsonl` | One line per decision: model, prompt version, prompt hash, redaction counts, verdict, latency |

Committed sample outputs:
- `samples/expected_output_rules/`: from the offline rules engine
- `samples/expected_output_claude/`: from Claude, produced by step 3 above

To refresh the Claude sample:

```bash
python -m failtriage run samples/nightly_run --out samples/expected_output_claude --no-cache
```

What the model receives is masked, e.g.
`accountNumber=<ACCOUNT> customerName="<REDACTED>" ... jdbc:postgresql://<USER>:<SECRET>@<IP>:5432/payments`.

---

## Use it on your own runs

Point it at any folder of JUnit-style or TestNG XML reports:

```bash
python -m failtriage run path/to/target/surefire-reports --out out
```

`history.json` and `context.json` are optional, but they improve accuracy a lot.
History separates flaky tests from real regressions. Context separates intentional changes (test bugs) from product bugs.

In CI, add a step after the test stage:

```yaml
- run: python -m failtriage run target/surefire-reports --out triage
  if: failure()
```

## Repository layout

```
failtriage/
  parser.py     JUnit / TestNG / PyTest XML → Failure objects (+ history)
  masker.py     PII / secret redaction before any LLM call (cards w/ Luhn, accounts, IBAN, BSB, emails, tokens, creds, IPs)
  clusterer.py  explainable root-cause grouping (no embeddings)
  rules.py      keyword baseline + offline engine
  llm.py        Claude call: versioned prompt, forced JSON schema, temperature 0, cache, confidence → review flag
  pipeline.py   orchestration, fallback to rules on API failure, reports, tickets, audit log
  evaluate.py   accuracy, macro-F1, confusion matrix, grouping F1, calibration, silent errors
data/build_dataset.py   generates the labelled evaluation run (32 root causes, 71 failures)
tests/                  pytest suite, with a fake Claude client and no network
```
