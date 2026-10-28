# Triage report — nightly_run

**36 failed tests → 12 distinct issues** (engine: `groq`, 301.19s, 0 flagged for human review)

| Category | Failed tests |
|---|---|
| 🐞 PRODUCT_BUG | 6 |
| 🧪 TEST_BUG | 7 |
| 🌩️ ENVIRONMENT | 20 |
| 🎲 FLAKY | 3 |

LLM calls: 12 (cache hits 0), tokens in/out: 23991/5881

## Issues (largest first)

| # | Group | Tests | Category | Conf. | Review? | Summary |
|---|---|---|---|---|---|---|
| 1 | C-b609a6ef | 8 | 🌩️ ENVIRONMENT | 0.95 | no | SIT payments DB (PostgreSQL) connection refused – all payments API tests return 503 |
| 2 | C-5d5b5bd3 | 5 | 🌩️ ENVIRONMENT | 0.95 | no | FX tests fail with 502: upstream rates.partner-sandbox.example.net returning 503 in SIT |
| 3 | C-ccefadee | 4 | 🌩️ ENVIRONMENT | 0.95 | no | Selenium grid exhausted (0/12 slots) causing SessionNotCreatedException in nightly UI run |
| 4 | C-7bc7d62b | 4 | 🧪 TEST_BUG | 0.97 | no | PaymentPage.submit() uses stale #submit-payment locator after UI-2231 |
| 5 | C-e8c5472d | 3 | 🌩️ ENVIRONMENT | 0.97 | no | SIT IdP client secret for qa-automation-sit expired 2026-10-27, breaking all API tests |
| 6 | C-259f8b9c | 3 | 🐞 PRODUCT_BUG | 0.95 | no | NPE in CrossRateCalculator.cross: usdLeg is null, causing 500 on /api/v1/fx/quote |
| 7 | C-5c292be3 | 3 | 🎲 FLAKY | 0.85 | no | TradeBlotterUiTest: StaleElementReferenceException from blotter auto-refresh race |
| 8 | C-5db9184e | 2 | 🐞 PRODUCT_BUG | 0.90 | no | Performance regression: trades-by-date query seq scan after TRD-912 index hint removal |
| 9 | C-84e92368 | 1 | 🧪 TEST_BUG | 0.85 | no | FeesApiTest.internationalTransferFee asserts stale fee 2.50 after FS-2026-10 loaded |
| 10 | C-5e3f5808 | 1 | 🐞 PRODUCT_BUG | 0.95 | no | Sanctioned-country payment (KP) accepted with screening SKIPPED instead of rejected 422 |
| 11 | C-1840080b | 1 | 🧪 TEST_BUG | 0.95 | no | test_statement_balance_format expects old 'AUD ' prefix after CR-1182 changed to 'A$' |
| 12 | C-e90ab83b | 1 | 🧪 TEST_BUG | 0.95 | no | Update test_transaction_amount_format expected value to new A$ format (CR-1182) |

Ticket drafts are in `tickets/`. Every decision is logged in `audit.jsonl`.
