# Triage report — nightly_run

**36 failed tests → 12 distinct issues** (engine: `rules`, 0.01s, 0 flagged for human review)

| Category | Failed tests |
|---|---|
| 🐞 PRODUCT_BUG | 10 |
| 🧪 TEST_BUG | 4 |
| 🌩️ ENVIRONMENT | 17 |
| 🎲 FLAKY | 5 |

## Issues (largest first)

| # | Group | Tests | Category | Conf. | Review? | Summary |
|---|---|---|---|---|---|---|
| 1 | C-b609a6ef | 8 | 🌩️ ENVIRONMENT | 0.70 | no | Matched environment pattern /\b50[234]\b/ |
| 2 | C-5d5b5bd3 | 5 | 🌩️ ENVIRONMENT | 0.70 | no | Matched environment pattern /\b50[234]\b/ |
| 3 | C-ccefadee | 4 | 🌩️ ENVIRONMENT | 0.70 | no | Matched environment pattern /grid status/ |
| 4 | C-7bc7d62b | 4 | 🧪 TEST_BUG | 0.65 | no | Matched locator/test pattern /nosuchelement/ |
| 5 | C-e8c5472d | 3 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /expected .* but (was/found)/ |
| 6 | C-259f8b9c | 3 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /\b500\b/ |
| 7 | C-5c292be3 | 3 | 🎲 FLAKY | 0.60 | no | History 'PPFPPPFPPF' flips 5 times |
| 8 | C-5db9184e | 2 | 🎲 FLAKY | 0.50 | no | Matched timing pattern /timeoutexception/ |
| 9 | C-84e92368 | 1 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /assert/ |
| 10 | C-5e3f5808 | 1 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /expected .* but (was/found)/ |
| 11 | C-1840080b | 1 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /assert/ |
| 12 | C-e90ab83b | 1 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /assert/ |

Ticket drafts are in `tickets/`. Every decision is logged in `audit.jsonl`.
