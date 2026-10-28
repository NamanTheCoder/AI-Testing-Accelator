"""Generate the labelled evaluation run and the small demo run.

The failures are SYNTHETIC but modelled on failure patterns from real banking
regression suites (Java/Selenium/TestNG UI, Rest Assured API, PyTest API).
Every root cause carries a ground-truth label and a note explaining it.
Run:  python data/build_dataset.py
Outputs:
  data/eval_run/       71 failing tests across 5 report files + history.json + context.json + labels.csv
  samples/nightly_run/ a 36-failure subset for the quick demo
"""
from __future__ import annotations

import csv
import json
import shutil
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "data" / "eval_run"
DEMO_DIR = ROOT / "samples" / "nightly_run"

STABLE = "PPPPPPPPPP"

RA = ["io.restassured.internal.ValidatableResponseImpl.statusCode(ValidatableResponseImpl.groovy:89)"]
TESTNG = ["org.testng.internal.invokers.MethodInvocationHelper.invokeMethod(MethodInvocationHelper.java:139)",
          "org.testng.internal.invokers.TestInvoker.invokeMethod(TestInvoker.java:677)"]
JUNIT = ["org.junit.jupiter.engine.execution.MethodInvocation.proceed(MethodInvocation.java:60)",
         "org.junit.platform.engine.support.hierarchical.NodeTestTask.execute(NodeTestTask.java:151)"]
SEL = ["org.openqa.selenium.remote.RemoteWebDriver.execute(RemoteWebDriver.java:597)",
       "org.openqa.selenium.remote.RemoteWebElement.execute(RemoteWebElement.java:285)"]


def jstack(exc: str, msg: str, frames: list[str], caused: str = "") -> str:
    s = f"{exc}: {msg}\n" + "\n".join(f"\tat {f}" for f in frames)
    return s + (f"\nCaused by: {caused}" if caused else "")


def pystack(frames: list[tuple[str, int, str, str]], exc: str, msg: str) -> str:
    out = ["Traceback (most recent call last):"]
    for path, line, fn, code in frames:
        out.append(f'  File "{path}", line {line}, in {fn}\n    {code}')
    out.append(f"{exc}: {msg}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Root causes. Each: id, label, report file, list of tests, failure builder, history, note.
# builder(test_class, test_method) -> dict(exception_type, message, stacktrace, log, duration)
# ---------------------------------------------------------------------------
RC: list[dict] = []


def rc(**kw):
    RC.append(kw)


API = "api-payments.xml"       # Surefire JUnit5 + Rest Assured
TRD = "api-trading.xml"        # Surefire JUnit5 + Rest Assured
COMP = "component-core.xml"    # in-process component tests (app code in stack)
PY = "pytest-statements.xml"   # PyTest --junitxml
UI = "testng-results.xml"      # Selenium/TestNG UI suite

# ---------------- ENVIRONMENT ----------------
rc(id="E1", label="ENVIRONMENT", report=API, demo=True,
   note="Payments DB in SIT was down overnight; every DB-touching API test fails the same way.",
   tests=[("com.northwind.qa.api.payments.TransferApiTest", m) for m in
          ["sameDayTransfer", "futureDatedTransfer", "transferToSavings", "cancelPendingTransfer"]] +
         [("com.northwind.qa.api.payments.PayeeApiTest", m) for m in
          ["addDomesticPayee", "deletePayee", "listPayees", "updatePayeeNickname"]],
   build=lambda c, m: dict(
       exception_type="java.lang.AssertionError",
       message="1 expectation failed. Expected status code <201> but was <503>.",
       stacktrace=jstack("java.lang.AssertionError",
                         "1 expectation failed.\nExpected status code <201> but was <503>.",
                         RA + [f"{c}.{m}({c.rsplit('.',1)[-1]}.java:58)"] + JUNIT),
       log=("2026-10-28T01:14:09.311Z INFO  POST /api/v1/payments/transfers accountNumber=062000123456 "
            "customerName=\"Priya Sharma\" email=priya.sharma@example.com\n"
            "2026-10-28T01:14:09.877Z ERROR payments-svc: org.postgresql.util.PSQLException: Connection to "
            "10.42.8.17:5432 refused. Check that the hostname and port are correct and that the postmaster "
            "is accepting TCP/IP connections. url=jdbc:postgresql://svc_payments:Sup3rS3cret@10.42.8.17:5432/payments\n"
            "2026-10-28T01:14:09.879Z WARN  HTTP 503 Service Unavailable {\"error\":\"DB_UNAVAILABLE\"}"),
       duration=1.2),
   history=STABLE)

rc(id="E2", label="ENVIRONMENT", report=TRD, demo=True,
   note="Third-party FX rates provider sandbox returning 503; not our code.",
   tests=[("com.northwind.qa.api.trading.FxQuoteApiTest", m) for m in
          ["quoteAudUsd", "quoteAudEur", "quoteExpiresAfter30s"]] +
         [("com.northwind.qa.api.trading.FxDealApiTest", m) for m in ["bookSpotDeal", "bookForwardDeal"]],
   build=lambda c, m: dict(
       exception_type="java.lang.AssertionError",
       message="1 expectation failed. Expected status code <200> but was <502>.",
       stacktrace=jstack("java.lang.AssertionError",
                         "1 expectation failed.\nExpected status code <200> but was <502>.",
                         RA + [f"{c}.{m}({c.rsplit('.',1)[-1]}.java:41)"] + JUNIT),
       log=("2026-10-28T01:20:44Z INFO  GET /api/v1/fx/quote?pair=AUDUSD\n"
            "2026-10-28T01:20:45Z ERROR fx-gateway: upstream rates.partner-sandbox.example.net responded 503 "
            "Service Unavailable (attempt 3/3)\n"
            "2026-10-28T01:20:45Z WARN  returning 502 Bad Gateway to caller"),
       duration=3.4),
   history=STABLE)

rc(id="E3", label="ENVIRONMENT", report=UI, demo=True,
   note="Selenium Grid node ran out of capacity; browser sessions could not be created.",
   tests=[("com.northwind.qa.ui.LoginUiTest", "loginWithMfa"),
          ("com.northwind.qa.ui.DashboardUiTest", "showsAccountTiles"),
          ("com.northwind.qa.ui.StatementsUiTest", "downloadPdfStatement"),
          ("com.northwind.qa.ui.StatementsUiTest", "filterByDateRange")],
   build=lambda c, m: dict(
       exception_type="org.openqa.selenium.SessionNotCreatedException",
       message="Could not start a new session. Response code 500. Message: Could not start a new session. "
               "No nodes support the capabilities in the request",
       stacktrace=jstack("org.openqa.selenium.SessionNotCreatedException",
                         "Could not start a new session. Response code 500. Message: Could not start a new "
                         "session. No nodes support the capabilities in the request",
                         ["org.openqa.selenium.remote.ProtocolHandshake.createSession(ProtocolHandshake.java:126)",
                          "org.openqa.selenium.remote.RemoteWebDriver.startSession(RemoteWebDriver.java:229)",
                          "com.northwind.qa.core.DriverFactory.create(DriverFactory.java:44)",
                          f"{c}.setUp(BaseUiTest.java:22)"] + TESTNG),
       log="Grid status: 0/12 slots free, queue size 37, request timed out after 300s",
       duration=300.4),
   history=STABLE)

rc(id="E4", label="ENVIRONMENT", report=PY, demo=False,
   note="Test-data pool exhausted (all ACTIVE accounts consumed by earlier runs).",
   tests=[("tests.statements.test_statements", m) for m in
          ["test_monthly_statement_totals", "test_statement_csv_export_headers", "test_interest_line_present"]],
   build=lambda c, m: dict(
       exception_type="testdata.pool.PoolExhaustedError",
       message="No eligible test account with status ACTIVE found in pool 'SIT-AU' (0 of 250 free)",
       stacktrace=pystack([("tests/statements/test_statements.py", 31, m, "acct = pool.checkout(status='ACTIVE')"),
                           ("testdata/pool.py", 88, "checkout", "raise PoolExhaustedError(...)")],
                          "testdata.pool.PoolExhaustedError",
                          "No eligible test account with status ACTIVE found in pool 'SIT-AU' (0 of 250 free)"),
       log="pool stats: total=250 leased=250 expired_leases=0 last_reset=2026-10-21",
       duration=0.3),
   history=STABLE)

rc(id="E5", label="ENVIRONMENT", report=API, demo=True,
   note="OAuth client secret for the SIT test client expired on 27 Oct; 401 invalid_client from the IdP. "
        "Rules engines tend to call any 401 a product bug.",
   tests=[("com.northwind.qa.api.payments.BpayApiTest", m) for m in ["payBillerByCode", "scheduleBpay"]] +
         [("com.northwind.qa.api.payments.DirectDebitApiTest", "createMandate")],
   build=lambda c, m: dict(
       exception_type="java.lang.AssertionError",
       message="1 expectation failed. Expected status code <200> but was <401>.",
       stacktrace=jstack("java.lang.AssertionError",
                         "1 expectation failed.\nExpected status code <200> but was <401>.",
                         RA + ["com.northwind.qa.core.AuthHelper.fetchToken(AuthHelper.java:37)",
                               f"{c}.{m}({c.rsplit('.',1)[-1]}.java:29)"] + JUNIT),
       log=("POST https://idp-sit.northwind.internal/oauth2/token grant_type=client_credentials "
            "client_id=qa-automation-sit client_secret=9f8e7d6c5b4a\n"
            "HTTP/1.1 401 {\"error\":\"invalid_client\",\"error_description\":\"Client secret has expired "
            "(expired 2026-10-27T00:00:00Z)\"}"),
       duration=0.6),
   history=STABLE)

rc(id="E6", label="ENVIRONMENT", report=COMP, demo=False,
   note="TLS certificate on the sanctions-screening stub expired.",
   tests=[("com.northwind.payments.SanctionsScreeningComponentTest", m) for m in
          ["screensBeneficiaryName", "blocksListedEntity"]],
   build=lambda c, m: dict(
       exception_type="javax.net.ssl.SSLHandshakeException",
       message="PKIX path validation failed: java.security.cert.CertPathValidatorException: "
               "validity check failed",
       stacktrace=jstack("javax.net.ssl.SSLHandshakeException",
                         "PKIX path validation failed: java.security.cert.CertPathValidatorException: validity check failed",
                         ["sun.security.ssl.Alert.createSSLException(Alert.java:131)",
                          "com.northwind.payments.sanctions.ScreeningClient.screen(ScreeningClient.java:52)",
                          f"{c}.{m}(SanctionsScreeningComponentTest.java:40)"] + JUNIT,
                         "java.security.cert.CertificateExpiredException: NotAfter: Mon Oct 27 23:59:59 UTC 2026"),
       log="Connecting to https://sanctions-stub.sit.northwind.internal:8443",
       duration=0.9),
   history=STABLE)

rc(id="E7", label="ENVIRONMENT", report=TRD, demo=False,
   note="Kafka broker in SIT unavailable, so settlement events never arrive and the test times out. "
        "The exception is a timeout; the cause is only visible in the log.",
   tests=[("com.northwind.qa.api.trading.SettlementEventTest", m) for m in
          ["publishesSettledEvent", "publishesFailedSettlementEvent"]],
   build=lambda c, m: dict(
       exception_type="org.awaitility.core.ConditionTimeoutException",
       message="Condition with lambda expression in com.northwind.qa.events.EventProbe was not fulfilled within 30 seconds.",
       stacktrace=jstack("org.awaitility.core.ConditionTimeoutException",
                         "Condition with lambda expression in com.northwind.qa.events.EventProbe was not fulfilled within 30 seconds.",
                         ["org.awaitility.core.ConditionAwaiter.await(ConditionAwaiter.java:167)",
                          "com.northwind.qa.events.EventProbe.awaitEvent(EventProbe.java:61)",
                          f"{c}.{m}(SettlementEventTest.java:48)"] + JUNIT),
       log=("[kafka-consumer-qa] WARN o.a.k.c.NetworkClient - [Consumer clientId=qa-probe] Connection to node -1 "
            "(kafka-sit-1.northwind.internal/10.42.9.3:9092) could not be established. Broker may not be available.\n"
            "[kafka-consumer-qa] WARN o.a.k.c.NetworkClient - Bootstrap broker kafka-sit-1:9092 disconnected"),
       duration=30.2),
   history=STABLE)

rc(id="E8", label="ENVIRONMENT", report=API, demo=False,
   note="Card-gateway sandbox is intermittently overloaded (503). History flips, but the cause is the "
        "environment, not the test. Rules that look at history first call this FLAKY.",
   tests=[("com.northwind.qa.api.payments.CardPaymentApiTest", m) for m in ["authoriseCard", "refundCard"]],
   build=lambda c, m: dict(
       exception_type="java.lang.AssertionError",
       message="1 expectation failed. Expected status code <200> but was <503>.",
       stacktrace=jstack("java.lang.AssertionError",
                         "1 expectation failed.\nExpected status code <200> but was <503>.",
                         RA + [f"{c}.{m}(CardPaymentApiTest.java:33)"] + JUNIT),
       log=("POST /api/v1/cards/authorise pan=4111 1111 1111 1111 expiry=12/28 amount=10.00\n"
            "card-gateway-sandbox: 503 Service Unavailable - Retry-After: 30 (sandbox capacity exceeded)"),
       duration=2.1),
   history="PPFPPFPPPF")

# ---------------- TEST_BUG ----------------
rc(id="T1", label="TEST_BUG", report=UI, demo=True,
   note="Intentional UI change (see context.json): submit button renamed/re-ided; locators not updated.",
   tests=[("com.northwind.qa.ui.PaymentsUiTest", m) for m in
          ["payNewPayee", "payExistingPayee", "payWithReference"]] +
         [("com.northwind.qa.ui.InternationalPaymentsUiTest", "payInEur")],
   build=lambda c, m: dict(
       exception_type="org.openqa.selenium.NoSuchElementException",
       message="no such element: Unable to locate element: {\"method\":\"css selector\",\"selector\":\"#submit-payment\"}",
       stacktrace=jstack("org.openqa.selenium.NoSuchElementException",
                         "no such element: Unable to locate element: {\"method\":\"css selector\",\"selector\":\"#submit-payment\"}",
                         SEL + ["com.northwind.qa.pages.PaymentPage.submit(PaymentPage.java:74)",
                                f"{c}.{m}({c.rsplit('.',1)[-1]}.java:51)"] + TESTNG),
       log="Page title: 'Review payment'; buttons on page: ['#review-confirm', '#cancel']",
       duration=12.8),
   history=STABLE)

rc(id="T2", label="TEST_BUG", report=PY, demo=True,
   note="Currency display format intentionally changed (CR-1182, in context.json); test still expects old format. "
        "Looks like a product assertion failure without the change context.",
   tests=[("tests.statements.test_formatting", "test_statement_balance_format"),
          ("tests.statements.test_formatting", "test_transaction_amount_format")],
   build=lambda c, m: dict(
       exception_type="AssertionError",
       message="assert 'A$1,000.00' == 'AUD 1,000.00'",
       stacktrace=pystack([("tests/statements/test_formatting.py", 22, m,
                            "assert row['display_amount'] == 'AUD 1,000.00'")],
                          "AssertionError", "assert 'A$1,000.00' == 'AUD 1,000.00'\n  - AUD 1,000.00\n  + A$1,000.00"),
       log="GET /api/v2/statements/latest -> 200 (fields: display_amount, currency, posted_at)",
       duration=0.4),
   history=STABLE)

rc(id="T3", label="TEST_BUG", report=UI, demo=False,
   note="NPE inside a page object (null WebElement list when grid is empty) - test code defect.",
   tests=[("com.northwind.qa.ui.TradeBlotterUiTest", m) for m in ["emptyBlotterShowsMessage", "filterBySymbol"]],
   build=lambda c, m: dict(
       exception_type="java.lang.NullPointerException",
       message="Cannot invoke \"java.util.List.size()\" because \"this.rows\" is null",
       stacktrace=jstack("java.lang.NullPointerException",
                         "Cannot invoke \"java.util.List.size()\" because \"this.rows\" is null",
                         ["com.northwind.qa.pages.TradeBlotterPage.getRowCount(TradeBlotterPage.java:88)",
                          f"{c}.{m}(TradeBlotterUiTest.java:37)"] + TESTNG),
       log="", duration=4.2),
   history=STABLE)

rc(id="T4", label="TEST_BUG", report=TRD, demo=False,
   note="Test-order dependency: a hard-coded order id is reused and the previous test does not clean up.",
   tests=[("com.northwind.qa.api.trading.OrderApiTest", "placeLimitOrder")],
   build=lambda c, m: dict(
       exception_type="java.lang.AssertionError",
       message="1 expectation failed. Expected status code <201> but was <409>.",
       stacktrace=jstack("java.lang.AssertionError", "1 expectation failed.\nExpected status code <201> but was <409>.",
                         RA + [f"{c}.{m}(OrderApiTest.java:44)"] + JUNIT),
       log=("POST /api/v1/orders {\"clientOrderId\":\"ORD-TEST-001\",\"symbol\":\"BHP\",\"qty\":100}\n"
            "409 {\"error\":\"DUPLICATE_CLIENT_ORDER_ID\",\"detail\":\"clientOrderId ORD-TEST-001 already exists "
            "(created 2026-10-28T01:31:02Z by OrderApiTest.amendLimitOrder)\"}"),
       duration=0.5),
   history="PPPPPPPPPP")

rc(id="T5", label="TEST_BUG", report=PY, demo=False,
   note="Test helper call signature out of date after a helper refactor in the test repo.",
   tests=[("tests.payments.test_transfers_api", m) for m in ["test_transfer_limits", "test_transfer_same_currency"]],
   build=lambda c, m: dict(
       exception_type="TypeError",
       message="build_transfer() missing 1 required positional argument: 'currency'",
       stacktrace=pystack([("tests/payments/test_transfers_api.py", 40, m, "payload = build_transfer(src, dst, 100)"),
                           ("tests/helpers/payload_builder.py", 12, "build_transfer", "def build_transfer(src, dst, amount, currency):")],
                          "TypeError", "build_transfer() missing 1 required positional argument: 'currency'"),
       log="", duration=0.01),
   history=STABLE)

rc(id="T6", label="TEST_BUG", report=API, demo=False,
   note="API v2 intentionally renamed $.data.balance to $.data.availableBalance (context.json); test JSON path is stale.",
   tests=[("com.northwind.qa.api.payments.AccountApiTest", m) for m in ["getBalance", "balanceAfterTransfer"]],
   build=lambda c, m: dict(
       exception_type="java.lang.IllegalArgumentException",
       message="No results for path: $['data']['balance']",
       stacktrace=jstack("java.lang.IllegalArgumentException", "No results for path: $['data']['balance']",
                         ["io.restassured.path.json.JsonPath.getJsonObject(JsonPath.java:1008)",
                          "com.northwind.qa.core.Json.read(Json.java:19)",
                          f"{c}.{m}(AccountApiTest.java:27)"] + JUNIT),
       log=("GET /api/v2/accounts/acct-7f3a/balance -> 200 "
            "{\"data\":{\"availableBalance\":1520.40,\"currentBalance\":1600.00,\"currency\":\"AUD\"}}"),
       duration=0.3),
   history=STABLE)

rc(id="T7", label="TEST_BUG", report=UI, demo=False,
   note="New sticky footer intentionally duplicates the Confirm button (context.json); the Playwright-style "
        "locator is now ambiguous. Test must be made specific.",
   tests=[("com.northwind.qa.ui.TermDepositUiTest", m) for m in ["openTermDeposit", "rolloverTermDeposit"]],
   build=lambda c, m: dict(
       exception_type="com.microsoft.playwright.PlaywrightException",
       message="Error: strict mode violation: getByRole(BUTTON, name=\"Confirm\") resolved to 2 elements",
       stacktrace=jstack("com.microsoft.playwright.PlaywrightException",
                         "Error: strict mode violation: getByRole(BUTTON, name=\"Confirm\") resolved to 2 elements",
                         ["com.microsoft.playwright.impl.LocatorImpl.click(LocatorImpl.java:142)",
                          "com.northwind.qa.pages.TermDepositPage.confirm(TermDepositPage.java:59)",
                          f"{c}.{m}(TermDepositUiTest.java:33)"] + TESTNG),
       log="1) <button id=\"td-confirm\">Confirm</button>  2) <button class=\"sticky-footer__cta\">Confirm</button>",
       duration=6.0),
   history=STABLE)

# ---------------- PRODUCT_BUG ----------------
rc(id="P1", label="PRODUCT_BUG", report=API, demo=True,
   note="International transfer fee calculated 10x too high.",
   tests=[("com.northwind.qa.api.payments.FeesApiTest", "internationalTransferFee")],
   build=lambda c, m: dict(
       exception_type="org.opentest4j.AssertionFailedError",
       message="Fee for USD 1000 international transfer ==> expected: <2.50> but was: <25.00>",
       stacktrace=jstack("org.opentest4j.AssertionFailedError",
                         "Fee for USD 1000 international transfer ==> expected: <2.50> but was: <25.00>",
                         ["org.junit.jupiter.api.AssertionUtils.fail(AssertionUtils.java:55)",
                          f"{c}.{m}(FeesApiTest.java:62)"] + JUNIT),
       log="GET /api/v1/fees/quote?type=INTL&amount=1000&ccy=USD -> 200 {\"fee\":25.00,\"feeSchedule\":\"FS-2026-10\"}",
       duration=0.4),
   history=STABLE)

rc(id="P2", label="PRODUCT_BUG", report=TRD, demo=True,
   note="Our FX quote service throws NPE for cross-currency pairs after the latest deploy (500).",
   tests=[("com.northwind.qa.api.trading.FxCrossRateApiTest", m) for m in ["quoteEurJpy", "quoteGbpNzd", "quoteChfSgd"]],
   build=lambda c, m: dict(
       exception_type="java.lang.AssertionError",
       message="1 expectation failed. Expected status code <200> but was <500>.",
       stacktrace=jstack("java.lang.AssertionError", "1 expectation failed.\nExpected status code <200> but was <500>.",
                         RA + [f"{c}.{m}(FxCrossRateApiTest.java:30)"] + JUNIT),
       log=("trading-svc ERROR [req-9a1f] Unhandled exception on GET /api/v1/fx/quote\n"
            "java.lang.NullPointerException: Cannot invoke \"java.math.BigDecimal.divide(java.math.BigDecimal, "
            "java.math.MathContext)\" because \"usdLeg\" is null\n"
            "\tat com.northwind.trading.fx.CrossRateCalculator.cross(CrossRateCalculator.java:77)\n"
            "\tat com.northwind.trading.fx.FxQuoteService.quote(FxQuoteService.java:41)"),
       duration=0.7),
   history=STABLE)

rc(id="P3", label="PRODUCT_BUG", report=COMP, demo=False,
   note="NPE in application code (daily-limit check) when customer has no limit override record.",
   tests=[("com.northwind.payments.LimitServiceComponentTest", m) for m in
          ["defaultLimitApplied", "limitResetsAtMidnight"]],
   build=lambda c, m: dict(
       exception_type="java.lang.NullPointerException",
       message="Cannot invoke \"com.northwind.payments.limits.LimitOverride.getAmount()\" because \"override\" is null",
       stacktrace=jstack("java.lang.NullPointerException",
                         "Cannot invoke \"com.northwind.payments.limits.LimitOverride.getAmount()\" because \"override\" is null",
                         ["com.northwind.payments.limits.LimitService.checkDailyLimit(LimitService.java:113)",
                          "com.northwind.payments.limits.LimitService.validate(LimitService.java:58)",
                          f"{c}.{m}(LimitServiceComponentTest.java:45)"] + JUNIT),
       log="", duration=0.2),
   history=STABLE)

rc(id="P4", label="PRODUCT_BUG", report=COMP, demo=False,
   note="Interest accrual rounding uses HALF_UP instead of the required banker's rounding (HALF_EVEN).",
   tests=[("com.northwind.payments.InterestAccrualComponentTest", "monthlyAccrualRounding")],
   build=lambda c, m: dict(
       exception_type="org.opentest4j.AssertionFailedError",
       message="expected: <1033.32> but was: <1033.33>",
       stacktrace=jstack("org.opentest4j.AssertionFailedError", "expected: <1033.32> but was: <1033.33>",
                         ["org.junit.jupiter.api.AssertionUtils.fail(AssertionUtils.java:55)",
                          f"{c}.{m}(InterestAccrualComponentTest.java:71)"] + JUNIT),
       log="accrual: principal=250000.00 rate=4.96% days=30 raw=1033.325 rounding=HALF_UP",
       duration=0.1),
   history=STABLE)

rc(id="P5", label="PRODUCT_BUG", report=API, demo=True,
   note="Business rule regression: transfer to a sanctioned-country beneficiary is accepted.",
   tests=[("com.northwind.qa.api.payments.ComplianceApiTest", "rejectsSanctionedCountry")],
   build=lambda c, m: dict(
       exception_type="java.lang.AssertionError",
       message="1 expectation failed. Expected status code <422> but was <201>.",
       stacktrace=jstack("java.lang.AssertionError", "1 expectation failed.\nExpected status code <422> but was <201>.",
                         RA + [f"{c}.{m}(ComplianceApiTest.java:39)"] + JUNIT),
       log=("POST /api/v1/payments/international beneficiaryCountry=KP amount=5000 -> 201 "
            "{\"paymentId\":\"pay-31c9\",\"status\":\"ACCEPTED\",\"screening\":\"SKIPPED\"}"),
       duration=0.6),
   history=STABLE)

rc(id="P6", label="PRODUCT_BUG", report=UI, demo=True,
   note="Real performance regression: trade query lost its index hint in the latest commit; page now takes ~41s. "
        "Surface symptom is a UI timeout, which rules call FLAKY.",
   tests=[("com.northwind.qa.ui.TradeBlotterUiTest", m) for m in ["loadsTodayTrades", "sortsByNotional"]],
   build=lambda c, m: dict(
       exception_type="org.openqa.selenium.TimeoutException",
       message="Expected condition failed: waiting for visibility of element located by By.cssSelector: "
               "#blotter-grid .row (tried for 30 second(s) with 500 milliseconds interval)",
       stacktrace=jstack("org.openqa.selenium.TimeoutException",
                         "Expected condition failed: waiting for visibility of element located by By.cssSelector: "
                         "#blotter-grid .row (tried for 30 second(s) with 500 milliseconds interval)",
                         ["org.openqa.selenium.support.ui.WebDriverWait.timeoutException(WebDriverWait.java:84)",
                          "com.northwind.qa.pages.TradeBlotterPage.waitForRows(TradeBlotterPage.java:41)",
                          f"{c}.{m}(TradeBlotterUiTest.java:25)"] + TESTNG),
       log=("browser network: GET /api/v1/trades?date=2026-10-27&limit=500 -> 200 in 41213 ms (p50 last 7 days: 820 ms)\n"
            "trading-svc WARN slow query 40987 ms: SELECT ... FROM trades WHERE trade_date = ? (seq scan on trades)"),
       duration=30.6),
   history=STABLE)

rc(id="P7", label="PRODUCT_BUG", report=PY, demo=False,
   note="Off-by-one: statement CSV export drops the last transaction.",
   tests=[("tests.statements.test_exports", "test_csv_contains_all_transactions")],
   build=lambda c, m: dict(
       exception_type="AssertionError",
       message="assert 11 == 12",
       stacktrace=pystack([("tests/statements/test_exports.py", 54, m, "assert len(rows) == len(seeded_txns)")],
                          "AssertionError", "assert 11 == 12\n +  where 11 = len([...])"),
       log="seeded 12 transactions for acct-2b91 (2026-10-01..2026-10-27); export returned 11 rows; missing id txn-0012 (2026-10-27)",
       duration=0.9),
   history=STABLE)

rc(id="P8", label="PRODUCT_BUG", report=API, demo=False,
   note="Idempotency broken: retried payment with same Idempotency-Key debits twice.",
   tests=[("com.northwind.qa.api.payments.IdempotencyApiTest", "retryDoesNotDoubleDebit")],
   build=lambda c, m: dict(
       exception_type="org.opentest4j.AssertionFailedError",
       message="debits for Idempotency-Key 6f1c... ==> expected: <1> but was: <2>",
       stacktrace=jstack("org.opentest4j.AssertionFailedError",
                         "debits for Idempotency-Key 6f1c... ==> expected: <1> but was: <2>",
                         ["org.junit.jupiter.api.AssertionUtils.fail(AssertionUtils.java:55)",
                          f"{c}.{m}(IdempotencyApiTest.java:48)"] + JUNIT),
       log="POST /api/v1/payments (attempt 1) -> 201 pay-77a0; POST /api/v1/payments (attempt 2, same key) -> 201 pay-77a1",
       duration=1.1),
   history=STABLE)

rc(id="P9", label="PRODUCT_BUG", report=API, demo=False,
   note="Endpoint accidentally removed in latest deploy (no intentional change listed): 404.",
   tests=[("com.northwind.qa.api.payments.LimitsApiTest", m) for m in ["getDailyLimit", "updateDailyLimit"]],
   build=lambda c, m: dict(
       exception_type="java.lang.AssertionError",
       message="1 expectation failed. Expected status code <200> but was <404>.",
       stacktrace=jstack("java.lang.AssertionError", "1 expectation failed.\nExpected status code <200> but was <404>.",
                         RA + [f"{c}.{m}(LimitsApiTest.java:24)"] + JUNIT),
       log="GET /api/v1/accounts/acct-7f3a/limits -> 404 {\"error\":\"No route\"}; /api/v1/accounts/acct-7f3a -> 200",
       duration=0.3),
   history=STABLE)

rc(id="P10", label="PRODUCT_BUG", report=TRD, demo=False,
   note="Cross rate inverted (returns USD/AUD instead of AUD/USD).",
   tests=[("com.northwind.qa.api.trading.FxRateApiTest", "audUsdRateDirection")],
   build=lambda c, m: dict(
       exception_type="org.opentest4j.AssertionFailedError",
       message="AUDUSD mid rate ==> expected: <0.6541> but was: <1.5288>",
       stacktrace=jstack("org.opentest4j.AssertionFailedError", "AUDUSD mid rate ==> expected: <0.6541> but was: <1.5288>",
                         ["org.junit.jupiter.api.AssertionUtils.fail(AssertionUtils.java:55)",
                          f"{c}.{m}(FxRateApiTest.java:35)"] + JUNIT),
       log="reference rate fixture AUDUSD=0.6541; service returned 1.5288 (=1/0.6541)",
       duration=0.2),
   history=STABLE)

rc(id="P11", label="PRODUCT_BUG", report=COMP, demo=False,
   note="Audit trail missing PAYMENT_APPROVED event (regulatory requirement).",
   tests=[("com.northwind.payments.AuditTrailComponentTest", "approvalIsAudited")],
   build=lambda c, m: dict(
       exception_type="org.opentest4j.AssertionFailedError",
       message="Audit events for pay-5e2d ==> expected event PAYMENT_APPROVED but found [PAYMENT_CREATED, PAYMENT_SENT]",
       stacktrace=jstack("org.opentest4j.AssertionFailedError",
                         "Audit events for pay-5e2d ==> expected event PAYMENT_APPROVED but found [PAYMENT_CREATED, PAYMENT_SENT]",
                         ["org.junit.jupiter.api.AssertionUtils.fail(AssertionUtils.java:55)",
                          f"{c}.{m}(AuditTrailComponentTest.java:52)"] + JUNIT),
       log="approver=ops.user@example.com approved pay-5e2d at 2026-10-28T01:40:11Z",
       duration=0.5),
   history=STABLE)

rc(id="P12", label="PRODUCT_BUG", report=PY, demo=False,
   note="Statements API stopped returning settlementDate (no intentional change). KeyError is raised in test "
        "code, so naive rules blame the test.",
   tests=[("tests.statements.test_statement_fields", m) for m in
          ["test_settlement_date_present", "test_settlement_after_posting"]],
   build=lambda c, m: dict(
       exception_type="KeyError",
       message="'settlementDate'",
       stacktrace=pystack([("tests/statements/test_statement_fields.py", 18, m, "settled = txn['settlementDate']")],
                          "KeyError", "'settlementDate'"),
       log=("GET /api/v2/statements/latest -> 200 first txn keys: "
            "['id','postedAt','amount','currency','display_amount','description']"),
       duration=0.4),
   history=STABLE)

# ---------------- FLAKY ----------------
rc(id="F1", label="FLAKY", report=UI, demo=True,
   note="Blotter auto-refresh re-renders rows mid-interaction; intermittent StaleElementReference.",
   tests=[("com.northwind.qa.ui.TradeBlotterUiTest", m) for m in ["amendTradeFromRow", "cancelTradeFromRow", "openTradeDetails"]],
   build=lambda c, m: dict(
       exception_type="org.openqa.selenium.StaleElementReferenceException",
       message="stale element reference: stale element not found in the current frame",
       stacktrace=jstack("org.openqa.selenium.StaleElementReferenceException",
                         "stale element reference: stale element not found in the current frame",
                         SEL + ["com.northwind.qa.pages.TradeBlotterPage.clickRow(TradeBlotterPage.java:66)",
                                f"{c}.{m}(TradeBlotterUiTest.java:58)"] + TESTNG),
       log="blotter auto-refresh fired at +2.1s (interval 2s)",
       duration=5.5),
   history="PPFPPPFPPF")

rc(id="F2", label="FLAKY", report=UI, demo=False,
   note="Toast disappears after 3s; test sometimes looks too late.",
   tests=[("com.northwind.qa.ui.PayeeUiTest", m) for m in ["addPayeeShowsToast", "deletePayeeShowsToast"]],
   build=lambda c, m: dict(
       exception_type="org.openqa.selenium.TimeoutException",
       message="Expected condition failed: waiting for visibility of element located by By.cssSelector: .toast-success "
               "(tried for 5 second(s) with 500 milliseconds interval)",
       stacktrace=jstack("org.openqa.selenium.TimeoutException",
                         "Expected condition failed: waiting for visibility of element located by By.cssSelector: .toast-success "
                         "(tried for 5 second(s) with 500 milliseconds interval)",
                         ["org.openqa.selenium.support.ui.WebDriverWait.timeoutException(WebDriverWait.java:84)",
                          "com.northwind.qa.pages.PayeePage.waitForToast(PayeePage.java:33)",
                          f"{c}.{m}(PayeeUiTest.java:40)"] + TESTNG),
       log="toast rendered at +0.4s, auto-dismissed at +3.4s; wait started at +3.6s",
       duration=5.6),
   history="PPPFPPPPFP")

rc(id="F3", label="FLAKY", report=TRD, demo=False,
   note="Asserts on ordering of two async events that have no ordering guarantee.",
   tests=[("com.northwind.qa.api.trading.TradeLifecycleTest", "eventsInOrder")],
   build=lambda c, m: dict(
       exception_type="org.opentest4j.AssertionFailedError",
       message="expected: <[CREATED, SETTLED]> but was: <[SETTLED, CREATED]>",
       stacktrace=jstack("org.opentest4j.AssertionFailedError", "expected: <[CREATED, SETTLED]> but was: <[SETTLED, CREATED]>",
                         ["org.junit.jupiter.api.AssertionUtils.fail(AssertionUtils.java:55)",
                          f"{c}.{m}(TradeLifecycleTest.java:71)"] + JUNIT),
       log="events consumed from 2 partitions: p0 CREATED@01:52:10.104 p1 SETTLED@01:52:10.101",
       duration=2.0),
   history="PFPPPPFPPP")

rc(id="F4", label="FLAKY", report=UI, demo=False,
   note="Loading spinner overlay intermittently intercepts the click.",
   tests=[("com.northwind.qa.ui.CardsUiTest", m) for m in ["freezeCard", "unfreezeCard"]],
   build=lambda c, m: dict(
       exception_type="org.openqa.selenium.ElementClickInterceptedException",
       message="element click intercepted: Element <button id=\"freeze\"> is not clickable at point (412, 388). "
               "Other element would receive the click: <div class=\"spinner-overlay\">",
       stacktrace=jstack("org.openqa.selenium.ElementClickInterceptedException",
                         "element click intercepted: Element <button id=\"freeze\"> is not clickable at point (412, 388). "
                         "Other element would receive the click: <div class=\"spinner-overlay\">",
                         SEL + ["com.northwind.qa.pages.CardsPage.toggleFreeze(CardsPage.java:47)",
                                f"{c}.{m}(CardsUiTest.java:29)"] + TESTNG),
       log="", duration=3.1),
   history="PPPPFPPPFP")

rc(id="F5", label="FLAKY", report=UI, demo=False,
   note="Chart render sometimes takes just over the 10s wait on a cold cache.",
   tests=[("com.northwind.qa.ui.PortfolioUiTest", "rendersPerformanceChart")],
   build=lambda c, m: dict(
       exception_type="org.openqa.selenium.TimeoutException",
       message="Expected condition failed: waiting for visibility of element located by By.id: portfolio-chart "
               "(tried for 10 second(s) with 500 milliseconds interval)",
       stacktrace=jstack("org.openqa.selenium.TimeoutException",
                         "Expected condition failed: waiting for visibility of element located by By.id: portfolio-chart "
                         "(tried for 10 second(s) with 500 milliseconds interval)",
                         ["org.openqa.selenium.support.ui.WebDriverWait.timeoutException(WebDriverWait.java:84)",
                          "com.northwind.qa.pages.PortfolioPage.waitForChart(PortfolioPage.java:28)",
                          f"{c}.{m}(PortfolioUiTest.java:19)"] + TESTNG),
       log="chart data API 200 in 9.6s (cold cache), chart visible at +10.4s",
       duration=10.5),
   history="PPPPPPPPFP")

CONTEXT = {
    "environment": "SIT",
    "run": "nightly-regression #1482, 2026-10-28 01:00 AEDT",
    "app_build": "northwind-platform 4.18.0-rc3",
    "recent_changes": [
        "UI-2231 Payments: 'Submit' button replaced by 'Review & confirm' (id #review-confirm) - intentional",
        "CR-1182 Display currency amounts as A$ instead of 'AUD ' prefix on statements - intentional",
        "API-588 Accounts API v2: $.data.balance renamed to $.data.availableBalance - intentional, documented",
        "UI-2240 Term deposits: added sticky footer with a second 'Confirm' CTA - intentional",
        "TRD-912 TradeQueryRepository: remove index hint from trades-by-date query (refactor)",
        "PAY-1301 Fee schedule FS-2026-10 loaded",
    ],
}


# ---------------------------------------------------------------------------
def _write_junit(path: Path, cases: list[dict], suite_name: str) -> None:
    ts = ET.Element("testsuites")
    s = ET.SubElement(ts, "testsuite", name=suite_name, tests=str(len(cases) + 40), failures=str(len(cases)))
    for k in cases:
        tc = ET.SubElement(s, "testcase", classname=k["cls"], name=k["method"], time=f"{k['duration']:.3f}")
        fail = ET.SubElement(tc, "failure", message=k["message"], type=k["exception_type"])
        fail.text = k["stacktrace"]
        if k["log"]:
            ET.SubElement(tc, "system-out").text = k["log"]
    # a few passing tests so the reports look real
    for i in range(3):
        ET.SubElement(s, "testcase", classname=f"com.northwind.qa.Smoke{i}", name="passes", time="0.1")
    ET.indent(ts)
    ET.ElementTree(ts).write(path, encoding="utf-8", xml_declaration=True)


def _write_testng(path: Path, cases: list[dict]) -> None:
    root = ET.Element("testng-results", total=str(len(cases) + 30), failed=str(len(cases)))
    suite = ET.SubElement(root, "suite", name="ui-regression")
    test = ET.SubElement(suite, "test", name="ui")
    by_cls: dict[str, list[dict]] = defaultdict(list)
    for k in cases:
        by_cls[k["cls"]].append(k)
    for cls, items in by_cls.items():
        ce = ET.SubElement(test, "class", name=cls)
        for k in items:
            m = ET.SubElement(ce, "test-method", status="FAIL", name=k["method"],
                              **{"duration-ms": str(int(k["duration"] * 1000))})
            ex = ET.SubElement(m, "exception", **{"class": k["exception_type"]})
            ET.SubElement(ex, "message").text = k["message"]
            ET.SubElement(ex, "full-stacktrace").text = k["stacktrace"]
            if k["log"]:
                out = ET.SubElement(m, "reporter-output")
                for line in k["log"].splitlines():
                    ET.SubElement(out, "line").text = line
        ET.SubElement(ce, "test-method", status="PASS", name="sanity", **{"duration-ms": "120"})
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def build(target: Path, only_demo: bool) -> int:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    by_report: dict[str, list[dict]] = defaultdict(list)
    labels, history = [], {}
    for r in RC:
        if only_demo and not r["demo"]:
            continue
        for cls, method in r["tests"]:
            d = r["build"](cls, method)
            case = dict(cls=cls, method=method, **d)
            by_report[r["report"]].append(case)
            tid = f"{cls}.{method}"
            history[tid] = r["history"]
            labels.append({"test_id": tid, "category": r["label"], "root_cause": r["id"], "note": r["note"]})
    for report, cases in by_report.items():
        if report == UI:
            _write_testng(target / report, cases)
        else:
            _write_junit(target / report, cases, report.replace(".xml", ""))
    (target / "history.json").write_text(json.dumps(history, indent=2))
    (target / "context.json").write_text(json.dumps(CONTEXT, indent=2))
    with (target / "labels.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["test_id", "category", "root_cause", "note"])
        w.writeheader()
        w.writerows(labels)
    return len(labels)


if __name__ == "__main__":
    n_eval = build(EVAL_DIR, only_demo=False)
    n_demo = build(DEMO_DIR, only_demo=True)
    print(f"eval run: {n_eval} failures, {len(RC)} root causes -> {EVAL_DIR.relative_to(ROOT)}")
    print(f"demo run: {n_demo} failures -> {DEMO_DIR.relative_to(ROOT)}")
