# Triage report — nightly_run

**36 failed tests → 3 distinct issues** (engine: `groq`, 78.82s, 1 flagged for human review)

| Category | Failed tests |
|---|---|
| 🐞 PRODUCT_BUG | 0 |
| 🧪 TEST_BUG | 0 |
| 🌩️ ENVIRONMENT | 17 |
| 🎲 FLAKY | 0 |

LLM calls: 2 (cache hits 0), tokens in/out: 4899/969

## Issues (largest first)

| # | Group | Tests | Category | Conf. | Review? | Summary |
|---|---|---|---|---|---|---|
| 1 | C-b609a6ef | 8 | 🌩️ ENVIRONMENT | 0.95 | no | SIT payments DB (PostgreSQL) connection refused – all payments API tests return 503 |
| 2 | C-5d5b5bd3 | 5 | 🌩️ ENVIRONMENT | 0.95 | no | FX tests fail with 502: upstream rates.partner-sandbox.example.net returning 503 in SIT |
| 3 | C-ccefadee | 4 | 🌩️ ENVIRONMENT | 0.70 | ⚠️ yes | [LLM unavailable: RateLimitError: Error code: 429 - {'error': {'message': 'Rate limit reac |

Ticket drafts are in `tickets/`. Every decision is logged in `audit.jsonl`.
