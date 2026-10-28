# AI-Testing-Accelator (failtriage) - Architecture

## Project Overview

**failtriage** is an AI-powered test failure triage system that automatically analyzes failing regression test runs and generates root cause analysis with draft Jira tickets.

**Purpose:** Transform red nightly runs into prioritized, actionable insights with minimal human intervention.

---

## System Architecture

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  INPUT: Test Reports & Metadata                                 │
│  ├─ JUnit/TestNG/PyTest XML files                              │
│  ├─ Test execution history (history.json)                       │
│  └─ Build context data (context.json)                           │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│  PROCESSING PIPELINE                                            │
│  ├─ parser.py: Parse test reports → Failure objects            │
│  ├─ masker.py: Redact PII & secrets                            │
│  ├─ clusterer.py: Group failures by root cause                │
│  ├─ rules.py: Apply heuristic rules baseline                   │
│  └─ llm.py: Claude/GROQ LLM classification                    │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│  OUTPUT: Triage Results                                         │
│  ├─ triage_report.md: Executive summary                        │
│  ├─ tickets/: Draft Jira tickets per issue                     │
│  ├─ triage_result.json: Machine-readable format                │
│  └─ audit.jsonl: Decision audit log                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. **Parser Module** (`failtriage/parser.py`)
- **Responsibility:** Convert test report formats to internal Failure objects
- **Inputs:** JUnit XML, TestNG XML, PyTest XML
- **Outputs:** Failure objects with metadata
- **Features:**
  - Parses surefire/rest-assured API reports
  - Handles TestNG Selenium UI reports
  - Processes PyTest reports
  - Enriches failures with execution history

### 2. **Masker Module** (`failtriage/masker.py`)
- **Responsibility:** Redact sensitive data before LLM processing
- **Detects & Masks:**
  - Payment card numbers (Luhn validation)
  - Account numbers (IBAN, BSB)
  - Customer names and emails
  - Database credentials and connection strings
  - IP addresses and tokens
- **Output:** Safe text safe for external LLM calls

### 3. **Clusterer Module** (`failtriage/clusterer.py`)
- **Responsibility:** Group failures by shared root causes
- **Method:** Explainable grouping (no embeddings)
- **Output:** Failure clusters with root cause labels
- **Benefits:** Reduces LLM calls, improves accuracy

### 4. **Rules Engine** (`failtriage/rules.py`)
- **Responsibility:** Offline heuristic classification
- **Function:** Keyword-based baseline without LLM costs
- **Output:** Classification and confidence scores
- **Fallback:** Used when LLM provider is unavailable

### 5. **LLM Integration** (`failtriage/llm.py`)
- **Responsibility:** Intelligent failure classification via Claude or GROQ
- **Providers:**
  - **Anthropic:** claude-sonnet-5-5 (default), claude-opus-5-5, claude-haiku-5-5
  - **GROQ:** mixtral-8x7b-32768, llama-3.1-70b-versatile, llama-3.1-8b-instant
- **Features:**
  - Versioned prompts
  - Forced JSON schema output
  - Temperature 0 (deterministic)
  - Prompt caching for cost reduction
  - Confidence scoring for review flags
  - Automatic provider detection from API keys

### 6. **Pipeline Orchestration** (`failtriage/pipeline.py`)
- **Responsibility:** Coordinate all processing steps
- **Features:**
  - Fail-safe fallback to rules engine
  - Report generation (markdown)
  - Ticket drafting
  - Audit logging
  - Error handling and recovery

### 7. **Evaluation Framework** (`failtriage/evaluate.py`)
- **Responsibility:** Measure accuracy against labeled data
- **Metrics:**
  - Classification accuracy
  - Macro-F1 score
  - Confusion matrix
  - Grouping F1
  - Confidence calibration
- **Output:** Detailed evaluation reports

---

## Data Models

### Failure Object
```
{
  test_name: str,
  failure_message: str,
  failure_type: str,          # AssertionError, RuntimeException, etc.
  stacktrace: str,
  root_cause: str,            # Determined by clusterer/LLM
  severity: str,              # product_bug, test_bug, env_issue, flaky_test
  confidence: float,          # 0.0 - 1.0
  requires_review: bool,      # True if confidence < threshold
  ticket_id: str              # Generated Jira ticket ID
}
```

### Audit Entry (JSONL)
```
{
  timestamp: ISO8601,
  test_name: str,
  model: str,                 # LLM model used
  prompt_version: str,
  prompt_hash: str,           # For reproducibility
  redaction_counts: dict,     # PII redaction stats
  verdict: str,               # Final classification
  confidence: float,
  latency_ms: int
}
```

---

## Configuration

### Environment Variables
```bash
# LLM Provider: Anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# LLM Provider: GROQ (Free models)
export GROQ_API_KEY=gsk_...

# Model selection
export TRIAGE_MODEL=claude-sonnet-5-5    # Or GROQ models
export LLM_PROVIDER=anthropic            # Or 'groq' (auto-detected)

# Review threshold
export TRIAGE_REVIEW_THRESHOLD=0.70      # Flag verdicts below this
```

### Optional Files
- `history.json`: Test execution history (last 10 runs per test)
- `context.json`: Build metadata and recent changes
- `.env`: Local configuration (git-ignored)

---

## Deployment & Execution

### Local Development
```bash
python -m failtriage run <test_reports_dir> --out <output_dir>
```

### CI/CD Integration
```yaml
- run: python -m failtriage run target/surefire-reports --out triage
  if: failure()
```

### Evaluation Mode
```bash
python -m failtriage eval data/eval_run --out results
```

### Testing
```bash
python -m pytest -q
```

---

## Security & Privacy

### PII Masking
- **Before:** Logs may contain sensitive data (cards, credentials, PII)
- **After:** All sensitive patterns redacted before LLM transmission
- **Audit:** Redaction counts logged for transparency

### API Key Management
- `.env` files excluded from version control
- Support for both Anthropic and GROQ free tiers
- No credentials logged in audit trail

### Data Flow
```
Raw Test Reports
       │
       ▼
    Parser
       │
       ▼
    Masker ◄─── Removes: Cards, Accounts, Creds, IPs, PII
       │
       ▼
Clusterer / LLM ◄─── Only safe, redacted data
       │
       ▼
    Results
```

---

## Performance Characteristics

### Processing Pipeline
1. **Parsing:** O(n) where n = test report size
2. **Masking:** O(n) single-pass redaction
3. **Clustering:** O(m²) where m = failure count (explainable grouping)
4. **LLM calls:** Batched by cluster (reduces API calls)
5. **Report generation:** O(m) markdown/ticket rendering

### Cost Optimization
- **GROQ:** Free tier suitable for testing and CI/CD
- **Anthropic:** Prompt caching reduces repeated calls
- **Fallback:** Rules engine provides offline capability
- **Batching:** Groups failures to minimize LLM invocations

### Typical Runtime
- **36 failures (sample):** ~1 minute with LLM
- **71 failures (evaluation):** 2-3 minutes with LLM
- **Offline mode:** <30 seconds for any dataset

---

## Repository Structure

```
failtriage/
├── __init__.py              # Package initialization
├── __main__.py              # CLI entry point
├── parser.py                # Test report parsing
├── masker.py                # PII/secret redaction
├── clusterer.py             # Root cause grouping
├── rules.py                 # Heuristic baseline
├── llm.py                   # LLM integration (Claude + GROQ)
├── models.py                # Data models
├── pipeline.py              # Orchestration
├── evaluate.py              # Evaluation metrics
└── (tests/)                 # Unit tests

data/
├── build_dataset.py         # Generates labeled evaluation set
└── eval_run/                # 32 root causes, 71 labeled failures

samples/
├── nightly_run/             # Realistic banking platform run
├── expected_output_rules/   # Rules engine baseline output
└── expected_output_claude/  # Claude LLM output

docs/
├── PROBLEM_STATEMENT.md     # Use case & problem definition
├── EVIDENCE.md              # Measurement methodology & results
└── LIMITS_AND_RISKS.md      # Limitations & mitigation strategies

tests/
└── test_failtriage.py       # Comprehensive pytest suite
```

---

## Integration Points

### Inputs
- **Test Frameworks:** JUnit, TestNG, PyTest
- **CI/CD:** Jenkins, GitHub Actions, GitLab CI
- **Version Control:** Git (for context)

### Outputs
- **Issue Tracking:** Jira (draft tickets)
- **Reporting:** Markdown reports, JSON APIs
- **Dashboards:** triage_result.json for BI tools

### LLM Providers
- **Anthropic Claude:** Production-grade, paid
- **GROQ:** Free, community models, good for testing

---

## Extensibility

### Adding New Test Formats
1. Extend `Parser` class in `parser.py`
2. Implement format-specific parsing logic
3. Return standardized `Failure` objects

### Adding New Redaction Rules
1. Extend `Masker` class in `masker.py`
2. Add regex patterns or detection logic
3. Update audit logging for new redaction types

### Adding New LLM Providers
1. Extend `llm.py` with provider-specific logic
2. Implement unified interface
3. Add environment variable detection
4. Update tests and documentation

---

## Quality Assurance

### Testing Strategy
- **Unit Tests:** Comprehensive pytest suite with fake LLM client
- **No Network Dependency:** All tests run offline
- **Evaluation Framework:** Accuracy metrics against labeled data
- **Regression Prevention:** CI integration prevents breaking changes

### Evaluation Metrics
- **Accuracy:** Correct classification rate
- **Macro-F1:** Per-category performance
- **Confusion Matrix:** Classification error analysis
- **Grouping F1:** Root cause clustering accuracy
- **Calibration:** Confidence score reliability

---

## Future Enhancements

1. **Multi-language Support:** Beyond English test failure messages
2. **Custom Models:** Fine-tuned models for specific domains
3. **Historical Trending:** Track root cause patterns over time
4. **Auto-Remediation:** Suggest or apply fixes automatically
5. **Team Integrations:** Slack notifications, Slack commands
6. **Custom Rules:** Domain-specific rule extensions

---

## Compliance & Standards

- **Security:** PII masking for regulated industries
- **Audit:** Complete audit trail of all decisions
- **Reproducibility:** Prompt versioning and hashing
- **Transparency:** Confidence scores and review flags

---

**Document Generated:** 2026-10-29
**Project:** AI-Testing-Accelator (failtriage)
**Repository:** https://github.com/NamanTheCoder/AI-Testing-Accelator
