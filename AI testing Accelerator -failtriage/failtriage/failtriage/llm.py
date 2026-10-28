"""Claude-based triage of one failure cluster.

Design choices that matter in a regulated environment:
  * Only MASKED text is ever placed in the prompt (see masker.py).
  * Output is forced through a tool schema, so we get validated JSON, not prose.
  * temperature=0 and a versioned prompt, so runs are as repeatable as possible
    and every verdict in the audit log can be traced to the exact prompt version.
  * The model is told it may say "not sure"; low confidence forces human review.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from .masker import mask_failure_fields
from .models import Category, Cluster, Verdict

PROMPT_VERSION = "triage-v1.2"
DEFAULT_MODEL = os.environ.get("TRIAGE_MODEL", "claude-sonnet-5-5")
REVIEW_THRESHOLD = float(os.environ.get("TRIAGE_REVIEW_THRESHOLD", "0.70"))
MAX_EXAMPLES_PER_CLUSTER = 3
STACK_CHARS = 3500
LOG_CHARS = 1500

SYSTEM_PROMPT = """You are a senior SDET triaging failures from an automated regression run at a bank.
Classify the ROOT CAUSE of a group of test failures that share one failure signature into exactly one category:

PRODUCT_BUG  - the application under test behaves incorrectly: wrong calculation/value returned, HTTP 500 from
               our own service, exception thrown from application (non-test) code, business rule violated,
               a real performance regression in our code.
TEST_BUG     - the automation itself is wrong: broken/outdated locator, wrong expected value after an
               INTENTIONAL change (check recent changes), bad wait/synchronisation logic that will always fail,
               exception thrown from test/page-object/fixture code, test-order dependency.
ENVIRONMENT  - infrastructure, configuration or test data: downstream/third-party service down (502/503/504),
               connection refused, DNS, certificates, DB/queue unavailable, grid/browser session failures,
               expired credentials in the test env, missing or consumed test data.
FLAKY        - non-deterministic: same test passes and fails with no relevant change (look at pass/fail
               history), race conditions, timing-sensitive waits that usually pass.

Decision rules:
- Pass/fail history is strong evidence. Frequent P/F alternation with no code change => FLAKY,
  unless the error clearly points to a service outage (=> ENVIRONMENT).
- A test that was passing consistently and now fails on every run after a change is NOT flaky.
- Timeouts are ambiguous: decide using history, which component was slow, and the logs. If you cannot decide,
  say so with low confidence.
- Prefer the most specific evidence (exception origin frame, HTTP status, log line) over the test name.
- Placeholders like <ACCOUNT>, <PAN>, <EMAIL>, <REDACTED> are masked sensitive data; never guess their values.
- Calibrate confidence honestly: 0.9+ only when evidence is unambiguous; below 0.7 when two categories are plausible.

Then draft a Jira ticket a developer could act on: concise summary, observed vs expected, evidence lines,
affected tests, suggested owner. Do not invent facts that are not in the input."""

TRIAGE_TOOL = {
    "name": "record_triage",
    "description": "Record the triage verdict for this failure group.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": Category.values()},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string", "description": "2-3 sentences explaining the decisive evidence."},
            "evidence": {"type": "array", "items": {"type": "string"},
                         "description": "Short verbatim lines from the input that support the verdict."},
            "alternative_category": {"type": "string", "enum": Category.values() + ["NONE"]},
            "suggested_owner": {"type": "string",
                                "description": "e.g. dev:<component>, qa:automation, platform/devops, test-data"},
            "jira_summary": {"type": "string", "description": "<= 100 chars"},
            "jira_description": {"type": "string", "description": "Markdown body for the ticket."},
        },
        "required": ["category", "confidence", "reason", "evidence", "alternative_category",
                     "suggested_owner", "jira_summary", "jira_description"],
    },
}


def build_payload(c: Cluster, run_context: dict | None = None) -> tuple[str, dict, list[str]]:
    """Return (masked user prompt, redaction counts, residual warnings)."""
    blocks = []
    all_counts: dict[str, int] = {}
    warnings: list[str] = []
    for i, f in enumerate(c.failures[:MAX_EXAMPLES_PER_CLUSTER], 1):
        masked, counts, warn = mask_failure_fields({
            "test_id": f.test_id,
            "exception": f.exception_type,
            "message": f.message,
            "stacktrace": f.stacktrace[:STACK_CHARS],
            "log": f.log_excerpt[-LOG_CHARS:],
        })
        for k, v in counts.items():
            all_counts[k] = all_counts.get(k, 0) + v
        warnings.extend(warn)
        blocks.append(
            f"### Failure {i}\n"
            f"test: {masked['test_id']}\n"
            f"duration_s: {f.duration_s}\n"
            f"history (oldest->newest, this run excluded): {f.history or 'unknown'}\n"
            f"exception: {masked['exception']}\n"
            f"message: {masked['message']}\n"
            f"stacktrace:\n{masked['stacktrace']}\n"
            f"log tail:\n{masked['log'] or '(none)'}\n"
        )
    ctx = ""
    if run_context:
        ctx_masked, counts, warn = mask_failure_fields({"ctx": json.dumps(run_context, indent=2)})
        for k, v in counts.items():
            all_counts[k] = all_counts.get(k, 0) + v
        warnings.extend(warn)
        ctx = f"## Run context\n{ctx_masked['ctx']}\n\n"
    others = c.test_ids[MAX_EXAMPLES_PER_CLUSTER:]
    prompt = (
        f"{ctx}## Failure group {c.cluster_id}\n"
        f"Signature: {c.signature}\n"
        f"Total failing tests in group: {len(c.failures)}\n"
        + (f"Other affected tests: {', '.join(others)}\n" if others else "")
        + "\n" + "\n".join(blocks)
    )
    return prompt, all_counts, warnings


class ClaudeTriager:
    def __init__(self, model: str = DEFAULT_MODEL, client=None, cache_dir: Path | None = None):
        self.model = model
        self._client = client
        self.cache_dir = cache_dir
        self.usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "cache_hits": 0}

    @property
    def client(self):
        if self._client is None:
            import anthropic  # imported lazily so --engine rules works without the SDK
            self._client = anthropic.Anthropic()
        return self._client

    def _cache_path(self, key: str) -> Path | None:
        return self.cache_dir / f"{key}.json" if self.cache_dir else None

    def classify(self, c: Cluster, run_context: dict | None = None) -> tuple[Verdict, dict]:
        prompt, counts, warnings = build_payload(c, run_context)
        key = hashlib.sha256(f"{self.model}|{PROMPT_VERSION}|{prompt}".encode()).hexdigest()[:24]
        meta = {"prompt_sha": key, "redactions": counts, "mask_warnings": warnings,
                "model": self.model, "prompt_version": PROMPT_VERSION}

        cp = self._cache_path(key)
        if cp and cp.exists():
            data = json.loads(cp.read_text())
            self.usage["cache_hits"] += 1
            meta.update(cached=True, latency_s=0.0)
        else:
            t0 = time.time()
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                temperature=0,
                system=SYSTEM_PROMPT,
                tools=[TRIAGE_TOOL],
                tool_choice={"type": "tool", "name": "record_triage"},
                messages=[{"role": "user", "content": prompt}],
            )
            meta["latency_s"] = round(time.time() - t0, 2)
            meta["cached"] = False
            u = getattr(resp, "usage", None)
            if u is not None:
                self.usage["input_tokens"] += getattr(u, "input_tokens", 0) or 0
                self.usage["output_tokens"] += getattr(u, "output_tokens", 0) or 0
            self.usage["calls"] += 1
            block = next(b for b in resp.content if getattr(b, "type", "") == "tool_use")
            data = dict(block.input)
            if cp:
                cp.parent.mkdir(parents=True, exist_ok=True)
                cp.write_text(json.dumps(data, indent=2))

        return self._to_verdict(data), meta

    def _to_verdict(self, d: dict) -> Verdict:
        cat = d.get("category")
        if cat not in Category.values():
            cat, conf = Category.PRODUCT_BUG.value, 0.0
        else:
            conf = max(0.0, min(1.0, float(d.get("confidence", 0))))
        alt = d.get("alternative_category", "NONE")
        reason = d.get("reason", "")
        if alt and alt not in ("NONE", cat):
            reason += f" (Alternative considered: {alt}.)"
        return Verdict(
            category=cat,
            confidence=conf,
            reason=reason,
            suggested_owner=d.get("suggested_owner", ""),
            evidence=list(d.get("evidence", []))[:6],
            needs_human_review=conf < REVIEW_THRESHOLD,
            jira_summary=d.get("jira_summary", "")[:120],
            jira_description=d.get("jira_description", ""),
            engine=f"claude:{self.model}",
        )
