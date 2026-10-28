# Triage report — quick_run

**5 failed tests → 3 distinct issues** (engine: `groq`, 6.19s, 0 flagged for human review)

| Category | Failed tests |
|---|---|
| 🐞 PRODUCT_BUG | 0 |
| 🧪 TEST_BUG | 2 |
| 🌩️ ENVIRONMENT | 3 |
| 🎲 FLAKY | 0 |

LLM calls: 3 (cache hits 0), tokens in/out: 5510/1417

## Issues (largest first)

| # | Group | Tests | Category | Conf. | Review? | Summary |
|---|---|---|---|---|---|---|
| 1 | C-b609a6ef | 3 | 🌩️ ENVIRONMENT | 0.95 | no | SIT payments DB connection refused causing 503 on all transfer API tests |
| 2 | C-1840080b | 1 | 🧪 TEST_BUG | 0.95 | no | test_statement_balance_format expects old 'AUD ' prefix after CR-1182 changed to 'A$' |
| 3 | C-e90ab83b | 1 | 🧪 TEST_BUG | 0.95 | no | Update test_transaction_amount_format expected value to new A$ format (CR-1182) |

Ticket drafts are in `tickets/`. Every decision is logged in `audit.jsonl`.
