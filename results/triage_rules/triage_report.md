# Triage report — eval_run [rules]

**71 failed tests → 34 distinct issues** (engine: `rules`, 0.01s, 3 flagged for human review)

| Category | Failed tests |
|---|---|
| 🐞 PRODUCT_BUG | 24 |
| 🧪 TEST_BUG | 10 |
| 🌩️ ENVIRONMENT | 22 |
| 🎲 FLAKY | 15 |

## Issues (largest first)

| # | Group | Tests | Category | Conf. | Review? | Summary |
|---|---|---|---|---|---|---|
| 1 | C-b609a6ef | 8 | 🌩️ ENVIRONMENT | 0.70 | no | Matched environment pattern /\b50[234]\b/ |
| 2 | C-5d5b5bd3 | 5 | 🌩️ ENVIRONMENT | 0.70 | no | Matched environment pattern /\b50[234]\b/ |
| 3 | C-ccefadee | 4 | 🌩️ ENVIRONMENT | 0.70 | no | Matched environment pattern /grid status/ |
| 4 | C-7bc7d62b | 4 | 🧪 TEST_BUG | 0.65 | no | Matched locator/test pattern /nosuchelement/ |
| 5 | C-e8c5472d | 3 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /expected .* but (was/found)/ |
| 6 | C-259f8b9c | 3 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /\b500\b/ |
| 7 | C-7310e240 | 3 | 🌩️ ENVIRONMENT | 0.70 | no | Matched environment pattern /no (eligible/available) test (account/data)/ |
| 8 | C-5c292be3 | 3 | 🎲 FLAKY | 0.60 | no | History 'PPFPPPFPPF' flips 5 times |
| 9 | C-c44c5ec6 | 2 | 🎲 FLAKY | 0.60 | no | History 'PPFPPFPPPF' flips 5 times |
| 10 | C-c2cd68a3 | 2 | 🐞 PRODUCT_BUG | 0.30 | ⚠️ yes | No rule matched; defaulting to product bug |
| 11 | C-3582adf2 | 2 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /expected .* but (was/found)/ |
| 12 | C-b90db00f | 2 | 🎲 FLAKY | 0.50 | no | Matched timing pattern /timeoutexception/ |
| 13 | C-35bb3db1 | 2 | 🌩️ ENVIRONMENT | 0.70 | no | Matched environment pattern /sslhandshake/ |
| 14 | C-a8bc84a7 | 2 | 🐞 PRODUCT_BUG | 0.55 | no | Null/type error at com.northwind.payments.limits.LimitService.checkDailyLimit(LimitService |
| 15 | C-e7ec78d4 | 2 | 🧪 TEST_BUG | 0.55 | no | Null/type error at tests/helpers/payload_builder.py:build_transfer |
| 16 | C-f74096e1 | 2 | 🧪 TEST_BUG | 0.55 | no | Null/type error at com.northwind.qa.pages.TradeBlotterPage.getRowCount(TradeBlotterPage.ja |
| 17 | C-5db9184e | 2 | 🎲 FLAKY | 0.50 | no | Matched timing pattern /timeoutexception/ |
| 18 | C-3cfd7e6b | 2 | 🧪 TEST_BUG | 0.65 | no | Matched locator/test pattern /strict mode violation/ |
| 19 | C-f3da7c7d | 2 | 🎲 FLAKY | 0.60 | no | History 'PPPFPPPPFP' flips 4 times |
| 20 | C-043e89b7 | 2 | 🎲 FLAKY | 0.60 | no | History 'PPPPFPPPFP' flips 4 times |
| 21 | C-84e92368 | 1 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /assert/ |
| 22 | C-5e3f5808 | 1 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /expected .* but (was/found)/ |
| 23 | C-d918e2bb | 1 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /assert/ |
| 24 | C-ac82265c | 1 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /expected .* but (was/found)/ |
| 25 | C-d76a27f6 | 1 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /assert/ |
| 26 | C-31472bfb | 1 | 🎲 FLAKY | 0.60 | no | History 'PFPPPPFPPP' flips 4 times |
| 27 | C-2e0ba45b | 1 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /assert/ |
| 28 | C-2ed30d66 | 1 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /expected .* but (was/found)/ |
| 29 | C-1840080b | 1 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /assert/ |
| 30 | C-e90ab83b | 1 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /assert/ |
| 31 | C-69b998de | 1 | 🐞 PRODUCT_BUG | 0.55 | no | Matched product pattern /assert/ |
| 32 | C-909a23a9 | 1 | 🐞 PRODUCT_BUG | 0.30 | ⚠️ yes | No rule matched; defaulting to product bug |
| 33 | C-453ff894 | 1 | 🐞 PRODUCT_BUG | 0.30 | ⚠️ yes | No rule matched; defaulting to product bug |
| 34 | C-381e94ac | 1 | 🎲 FLAKY | 0.50 | no | Matched timing pattern /timeoutexception/ |

Ticket drafts are in `tickets/`. Every decision is logged in `audit.jsonl`.
