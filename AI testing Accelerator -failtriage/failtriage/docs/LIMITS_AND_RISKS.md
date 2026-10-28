# Limits and risks

## Where the tool gets it wrong

| Weak spot | Why | Mitigation in this repo |
|---|---|---|
| **Timeouts** | A timeout can be flaky, environment, or a real performance regression. The exception looks identical. | History and log lines go into the prompt. The prompt says timeouts are ambiguous. Low confidence → review. Still the most likely error. |
| **Intentional vs accidental change** | "Expected X but was Y" is a test bug if the change was intended, and a product bug if not. The model only knows what `context.json` tells it. | Feed it the real change list (Jira fix-versions, merged PR titles). Without that, it guesses. |
| **First-time failures** | No history means FLAKY vs PRODUCT_BUG is guesswork. | `history.json` from the CI server. New tests should start with a lower auto-accept threshold. |
| **Over-grouping / under-grouping** | Grouping is signature-based. Two different bugs behind the same 500 can merge; one outage that throws different messages can split. | Grouping is explainable (the signature is shown). Assertion failures are never merged across tests. Reviewers can split groups. |
| **Confident but wrong** | LLM confidence is self-reported, not a probability. | The threshold is tuned on the eval set. "Silent errors" is a first-class metric. Re-measure on real data before trusting the number. |
| **Masking misses** | Regex masking cannot recognise every customer name or new identifier format. | Luhn-checked PANs, labelled fields, credentials in URLs, tokens. Unlabelled long numbers are *flagged*. A test asserts that no planted secret reaches any prompt. |
| **Hallucinated ticket detail** | Drafts can state plausible things not in the evidence. | The prompt forbids invented facts. Evidence lines are shown separately. Every ticket is marked DRAFT. |
| **Prompt injection via logs** | Test logs may contain attacker-controlled text, e.g. a payee name such as "ignore previous instructions". | Output is forced into a fixed schema with an enum category. The tool never takes actions, only drafts. |

## What a human still needs to check

- **Every PRODUCT_BUG verdict** before a ticket is filed. A wrong one wastes developer time and erodes trust.
- **Every FLAKY or ENVIRONMENT verdict on a test that touches money movement, limits, sanctions/AML or audit.** Dismissing a real defect is the expensive error. Such tests should be tagged so the tool always routes them to review.
- **All flagged groups** (confidence below the threshold, or the LLM was unavailable and rules were used).
- **Group boundaries** for the biggest groups. One wrong merge hides a defect behind an outage.
- **A weekly sample of auto-accepted verdicts**, to measure drift in production rather than trust the eval set forever.

## What I would change before using it in a bank

1. **Data residency and vendor approval.** Run Claude through the bank's approved route: an enterprise agreement with zero data retention, or via AWS Bedrock / Google Vertex in the bank's own region and tenant, behind the API gateway. Register it in the third-party risk and model inventory.
2. **Stronger redaction.** Replace or augment the regex masker with the bank's DLP service or a named-entity model. Add customer-name and address detection. Block the call, rather than just warn, when residual identifiers are found. Mask on the CI agent so raw logs never leave the build network.
3. **Least-privilege integration.** Read-only access to CI artefacts. Ticket creation stays human-approved: the tool writes drafts, a person clicks "file". No write access to Jira, Git or environments.
4. **Model risk management.** Treat the triager as a model under model risk policy:
   - document its intended use and limitations
   - keep the labelled eval set as a regression suite in CI
   - re-validate on every model or prompt version change (both are already logged)
   - set an accuracy and silent-error gate that a change must pass
5. **Audit and retention.** Ship `audit.jsonl` to the central log store with the bank's retention period. Add the reviewer's decision (accepted / overridden) so overrides become new labelled data.
6. **Validate on real history.** Before any rollout, run it in shadow mode for 2–4 weeks next to the human triager. Compare verdicts and only then let it pre-sort.
7. **Critical-path tagging.** Mark tests for payments, limits, sanctions, statements and audit as `critical`. For those, the tool may sort and draft, but never auto-accept FLAKY or ENVIRONMENT.
8. **Cost and resilience.** Cache by prompt hash (already done), cap tokens per run, and alert on spend. Rules fallback already applies on API failure, so a provider outage never blocks sign-off. Pin the model version.
