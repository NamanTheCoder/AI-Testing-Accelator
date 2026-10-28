# Problem statement

## The problem

Every night our regression suites run against SIT. They cover Selenium/TestNG UI, Rest Assured API and PyTest service tests.
On a bad night, dozens of tests go red. The red count by itself tells nobody what to do.

In practice those failures come from a handful of root causes, and they fall into four very different buckets:

| Bucket | Owner |
|---|---|
| Real product defects | developers |
| Broken tests (stale locators, outdated expected values after an intentional change) | automation engineers |
| Environment problems (a database down, a third-party sandbox returning 503, an expired certificate or client secret, an exhausted test-data pool) | platform / DevOps |
| Genuinely flaky tests | automation engineers |

Until someone sorts the failures into those buckets, the run cannot be signed off and nobody can act on it.

## Who has it

- **The automation lead / SDET on triage duty.** Usually the first person in each morning. They spend [~1–2 hours] reading stack traces and logs before stand-up.
- **Developers.** They lose time on tickets that turn out to be environment or test problems.
- **Release managers.** They wait on a go/no-go that depends on triage.
- **The team overall.** Flaky and environment noise erodes trust in automation ("it's probably just flaky"). That is exactly how real defects slip through.

This hurts most in a bank. Shared SIT environments depend on many downstream systems: payment gateways, FX rate providers, sanctions screening, message queues. So environment noise is high, and the cost of dismissing a real defect is high too.

## How it was handled before

**Manually.**

1. Open the Allure / Surefire / TestNG report.
2. Click into each failure and read the stack trace.
3. Grep the logs.
4. Check the pass/fail history in Jenkins.
5. Ask in chat whether SIT is down.
6. Mentally group failures that look alike.
7. Hand-write Jira tickets.

Some teams add keyword rules on top ("contains 503 → environment", "TimeoutException → flaky"). These are fast, but they are wrong in exactly the expensive cases:
- a performance regression that surfaces as a UI timeout gets dismissed as flaky
- an expired OAuth secret that returns 401 gets raised as a product bug
- an assertion broken by an intentional, documented change gets sent to developers

Triage quality depends on who is on duty, and the reasoning is rarely recorded.

## What this tool changes

**failtriage** reads the run's XML reports, pass/fail history and recent change list.
- It masks sensitive data and groups failures that share a root cause.
- Claude classifies each group with a reason, evidence and a calibrated confidence. Low-confidence verdicts are flagged for a human.
- It drafts a Jira ticket per issue for a human to approve, and logs every decision for audit.

The triager's job moves from *reading 70 stack traces* to *reviewing about 30 pre-sorted issues and the few that are flagged*.
