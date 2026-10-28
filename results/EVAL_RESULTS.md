# Evaluation results (71 labelled failures)

| Metric | rules baseline |
|---|---|
| Time to triage the whole run | 0.0 s |
| Issues to look at (groups) | 34 (true: 32) |
| Category accuracy (per test) | 80% |
| Macro-F1 | 0.79 |
| Grouping pairwise F1 | 0.99 |
| Auto-accepted (not flagged) | 94% |
| Accuracy when confident | 82% |
| Wrong AND not flagged (silent errors) | 12 |
| LLM tokens in/out | n/a |

## rules baseline: per-category

| Category | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| PRODUCT_BUG | 0.67 | 0.89 | 0.76 | 18 |
| TEST_BUG | 1.00 | 0.67 | 0.80 | 15 |
| ENVIRONMENT | 1.00 | 0.76 | 0.86 | 29 |
| FLAKY | 0.60 | 1.00 | 0.75 | 9 |

Confusion matrix (rows = truth, cols = predicted):

| truth \ pred | PRODUCT_BUG | TEST_BUG | ENVIRONMENT | FLAKY |
|---|---|---|---|---|
| PRODUCT_BUG | 16 | 0 | 0 | 2 |
| TEST_BUG | 5 | 10 | 0 | 0 |
| ENVIRONMENT | 3 | 0 | 22 | 4 |
| FLAKY | 0 | 0 | 0 | 9 |

Misclassified tests:

| Test | Truth | Predicted | Flagged? | Why it is hard |
|---|---|---|---|---|
| `BpayApiTest.payBillerByCode` | ENVIRONMENT | PRODUCT_BUG | **no** | OAuth client secret for the SIT test client expired on 27 Oct; 401 invalid_client from the IdP. Rules engines tend to call any 401 a product bug. |
| `BpayApiTest.scheduleBpay` | ENVIRONMENT | PRODUCT_BUG | **no** | OAuth client secret for the SIT test client expired on 27 Oct; 401 invalid_client from the IdP. Rules engines tend to call any 401 a product bug. |
| `DirectDebitApiTest.createMandate` | ENVIRONMENT | PRODUCT_BUG | **no** | OAuth client secret for the SIT test client expired on 27 Oct; 401 invalid_client from the IdP. Rules engines tend to call any 401 a product bug. |
| `SettlementEventTest.publishesSettledEvent` | ENVIRONMENT | FLAKY | **no** | Kafka broker in SIT unavailable, so settlement events never arrive and the test times out. The exception is a timeout; the cause is only visible in the log. |
| `SettlementEventTest.publishesFailedSettlementEvent` | ENVIRONMENT | FLAKY | **no** | Kafka broker in SIT unavailable, so settlement events never arrive and the test times out. The exception is a timeout; the cause is only visible in the log. |
| `CardPaymentApiTest.authoriseCard` | ENVIRONMENT | FLAKY | **no** | Card-gateway sandbox is intermittently overloaded (503). History flips, but the cause is the environment, not the test. Rules that look at history first call this FLAKY. |
| `CardPaymentApiTest.refundCard` | ENVIRONMENT | FLAKY | **no** | Card-gateway sandbox is intermittently overloaded (503). History flips, but the cause is the environment, not the test. Rules that look at history first call this FLAKY. |
| `test_formatting.test_statement_balance_format` | TEST_BUG | PRODUCT_BUG | **no** | Currency display format intentionally changed (CR-1182, in context.json); test still expects old format. Looks like a product assertion failure without the change context. |
| `test_formatting.test_transaction_amount_format` | TEST_BUG | PRODUCT_BUG | **no** | Currency display format intentionally changed (CR-1182, in context.json); test still expects old format. Looks like a product assertion failure without the change context. |
| `OrderApiTest.placeLimitOrder` | TEST_BUG | PRODUCT_BUG | **no** | Test-order dependency: a hard-coded order id is reused and the previous test does not clean up. |
| `AccountApiTest.getBalance` | TEST_BUG | PRODUCT_BUG | yes | API v2 intentionally renamed $.data.balance to $.data.availableBalance (context.json); test JSON path is stale. |
| `AccountApiTest.balanceAfterTransfer` | TEST_BUG | PRODUCT_BUG | yes | API v2 intentionally renamed $.data.balance to $.data.availableBalance (context.json); test JSON path is stale. |
| `TradeBlotterUiTest.loadsTodayTrades` | PRODUCT_BUG | FLAKY | **no** | Real performance regression: trade query lost its index hint in the latest commit; page now takes ~41s. Surface symptom is a UI timeout, which rules call FLAKY. |
| `TradeBlotterUiTest.sortsByNotional` | PRODUCT_BUG | FLAKY | **no** | Real performance regression: trade query lost its index hint in the latest commit; page now takes ~41s. Surface symptom is a UI timeout, which rules call FLAKY. |
