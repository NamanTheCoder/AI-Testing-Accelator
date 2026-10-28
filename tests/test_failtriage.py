"""Unit tests. No network: the Claude client is replaced by a fake."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from failtriage import rules
from failtriage.clusterer import cluster, normalise_message
from failtriage.evaluate import load_labels, score
from failtriage.llm import ClaudeTriager, GroqTriager, build_payload
from failtriage.masker import mask
from failtriage.models import Cluster, Failure, Verdict
from failtriage.parser import parse_run
from failtriage.pipeline import triage, write_outputs

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "data" / "eval_run"

# Sensitive strings planted in the synthetic logs. None may ever reach a prompt.
PLANTED_SECRETS = ["062000123456", "Priya", "Sharma", "priya.sharma@example.com", "ops.user@example.com",
                   "Sup3rS3cret", "svc_payments", "9f8e7d6c5b4a", "4111 1111 1111 1111", "10.42.8.17"]


@pytest.fixture(scope="module")
def failures():
    return parse_run(EVAL)


class FakeClient:
    """Mimics anthropic.Anthropic().messages.create(...) returning a forced tool_use block."""

    def __init__(self, answer: dict | None = None, raise_exc: Exception | None = None):
        self.answer = answer or {}
        self.raise_exc = raise_exc
        self.prompts: list[str] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.prompts.append(kw["messages"][0]["content"])
        assert kw["tool_choice"] == {"type": "tool", "name": "record_triage"}
        assert kw["temperature"] == 0
        if self.raise_exc:
            raise self.raise_exc
        block = SimpleNamespace(type="tool_use", input={
            "category": "ENVIRONMENT", "confidence": 0.9, "reason": "db down",
            "evidence": ["Connection refused"], "alternative_category": "NONE",
            "suggested_owner": "platform/devops", "jira_summary": "SIT payments DB unreachable",
            "jira_description": "...", **self.answer})
        return SimpleNamespace(content=[block], usage=SimpleNamespace(input_tokens=1000, output_tokens=200))


class FakeGroqClient:
    """Mimics groq.Groq().chat.completions.create(...) returning a tool_call."""

    def __init__(self, answer: dict | None = None, raise_exc: Exception | None = None):
        self.answer = answer or {}
        self.raise_exc = raise_exc
        self.prompts: list[str] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.prompts.append(kw["messages"][1]["content"])
        if self.raise_exc:
            raise self.raise_exc
        data = {
            "category": "ENVIRONMENT", "confidence": 0.9, "reason": "db down",
            "evidence": ["Connection refused"], "alternative_category": "NONE",
            "suggested_owner": "platform/devops", "jira_summary": "SIT payments DB unreachable",
            "jira_description": "...", **self.answer
        }
        tool_call = SimpleNamespace(
            id="call_1",
            function=SimpleNamespace(name="record_triage", arguments=json.dumps(data))
        )
        msg = SimpleNamespace(tool_calls=[tool_call], content=None)
        choice = SimpleNamespace(message=msg)
        return SimpleNamespace(choices=[choice], usage=SimpleNamespace(prompt_tokens=800, completion_tokens=150))


# ---------------- parser ----------------
def test_parses_all_labelled_failures(failures):
    labels = load_labels(EVAL)
    assert {f.test_id for f in failures} == set(labels)
    assert len(failures) == 71


def test_parser_reads_testng_and_junit_fields(failures):
    by_id = {f.test_id: f for f in failures}
    ui = by_id["com.northwind.qa.ui.PaymentsUiTest.payNewPayee"]          # TestNG
    assert ui.exception_type.endswith("NoSuchElementException") and "#submit-payment" in ui.message
    assert "review-confirm" in ui.log_excerpt and ui.duration_s > 0
    api = by_id["com.northwind.qa.api.payments.TransferApiTest.sameDayTransfer"]  # JUnit
    assert "<503>" in api.message and "PSQLException" in api.log_excerpt
    assert by_id["com.northwind.qa.ui.TradeBlotterUiTest.amendTradeFromRow"].history == "PPFPPPFPPF"


# ---------------- masking ----------------
@pytest.mark.parametrize("raw,must_vanish,placeholder", [
    ("pan=4111 1111 1111 1111 expiry", "4111 1111", "<PAN>"),
    ("card 5555555555554444 ok", "5555555555554444", "<PAN>"),
    ("mail priya.sharma@example.com now", "priya.sharma", "<EMAIL>"),
    ("accountNumber=062000123456", "062000123456", "<ACCOUNT>"),
    ('{"customerName": "Priya Sharma"}', "Priya", "<REDACTED>"),
    ("jdbc:postgresql://svc:Sup3rS3cret@db:5432/x", "Sup3rS3cret", "<SECRET>"),
    ("Authorization: Bearer abc.def-123", "abc.def-123", "<TOKEN>"),
    ("client_secret=9f8e7d6c5b4a&x=1", "9f8e7d6c5b4a", "<REDACTED>"),
    ("IBAN GB82 WEST 1234 5698 7654 32", "WEST 1234", "<IBAN>"),
])
def test_mask_removes_sensitive_values(raw, must_vanish, placeholder):
    r = mask(raw)
    assert must_vanish not in r.text and placeholder in r.text


def test_mask_keeps_non_luhn_numbers_but_flags_them():
    r = mask("orderRef 1234567890123456 failed")
    assert "<PAN>" not in r.text
    assert r.residual_warnings, "long unlabelled number should be flagged for review"


def test_mask_leaves_diagnostics_intact():
    text = "Expected status code <200> but was <503>. Connection to host:5432 refused"
    assert mask(text).text == text


def test_no_planted_secret_reaches_any_prompt(failures):
    ctx = json.loads((EVAL / "context.json").read_text())
    for c in cluster(failures):
        prompt, _, _ = build_payload(c, ctx)
        for s in PLANTED_SECRETS:
            assert s not in prompt, f"{s!r} leaked into prompt for {c.cluster_id}"


# ---------------- clustering ----------------
def test_db_outage_collapses_to_one_group(failures):
    groups = cluster(failures)
    db = [c for c in groups if any("TransferApiTest.sameDayTransfer" in t for t in c.test_ids)][0]
    assert len(db.failures) == 8  # 8 tests across 2 classes, one root cause
    assert len(groups) < len(failures) / 2


def test_assertion_failures_are_not_merged_across_tests():
    a = Failure("A.t1", "expected: <1> but was: <2>", "org.opentest4j.AssertionFailedError")
    b = Failure("B.t2", "expected: <3> but was: <4>", "org.opentest4j.AssertionFailedError")
    assert len(cluster([a, b])) == 2


def test_normalise_strips_volatile_tokens():
    m1 = normalise_message("Timeout at 2026-10-28T01:14:09Z for id 3f2a9c1e-1111-2222-3333-444455556666 after 30 s")
    m2 = normalise_message("Timeout at 2026-10-29T03:00:00Z for id 9a9a9a9a-1111-2222-3333-444455556666 after 45 s")
    assert m1 == m2


# ---------------- rules baseline ----------------
def test_rules_flaky_from_history():
    c = Cluster("c", "s", [Failure("T.x", "boom", "X", history="PFPFPPFPPF")])
    assert rules.classify_cluster(c).category == "FLAKY"


def test_rules_unknown_defaults_to_product_with_review():
    v = rules.classify_cluster(Cluster("c", "s", [Failure("T.x", "weird", "Weird")]))
    assert v.category == "PRODUCT_BUG" and v.needs_human_review


# ---------------- LLM wrapper ----------------
def test_claude_verdict_parsed_and_usage_counted(failures):
    t = ClaudeTriager(model="test-model", client=FakeClient())
    v, meta = t.classify(cluster(failures)[0])
    assert v.category == "ENVIRONMENT" and v.engine == "claude:test-model" and not v.needs_human_review
    assert meta["prompt_version"] and meta["redactions"]  # biggest cluster is the DB outage: redactions happened
    assert t.usage == {"input_tokens": 1000, "output_tokens": 200, "calls": 1, "cache_hits": 0}


def test_groq_verdict_parsed_and_usage_counted(failures):
    t = GroqTriager(model="test-groq-model", client=FakeGroqClient())
    v, meta = t.classify(cluster(failures)[0])
    assert v.category == "ENVIRONMENT" and v.engine == "groq:test-groq-model" and not v.needs_human_review
    assert meta["prompt_version"] and meta["redactions"]
    assert t.usage == {"input_tokens": 800, "output_tokens": 150, "calls": 1, "cache_hits": 0}


def test_low_confidence_forces_human_review(failures):
    t = ClaudeTriager(client=FakeClient({"confidence": 0.55, "alternative_category": "FLAKY"}))
    v, _ = t.classify(cluster(failures)[0])
    assert v.needs_human_review and "FLAKY" in v.reason


def test_invalid_category_from_model_is_neutralised(failures):
    t = ClaudeTriager(client=FakeClient({"category": "DEFINITELY_FINE"}))
    v, _ = t.classify(cluster(failures)[0])
    assert v.confidence == 0.0 and v.needs_human_review


def test_cache_prevents_repeat_calls(failures, tmp_path):
    fake = FakeClient()
    t = ClaudeTriager(client=fake, cache_dir=tmp_path)
    c = cluster(failures)[0]
    t.classify(c)
    t.classify(c)
    assert len(fake.prompts) == 1 and t.usage["cache_hits"] == 1


def test_api_failure_falls_back_to_rules_and_flags(failures, tmp_path):
    t = ClaudeTriager(client=FakeClient(raise_exc=RuntimeError("529 overloaded")))
    clusters, stats = triage(failures[:5], engine="claude", triager=t, audit_path=tmp_path / "a.jsonl")
    assert all(c.verdict.needs_human_review and "LLM unavailable" in c.verdict.reason for c in clusters)
    rows = [json.loads(x) for x in (tmp_path / "a.jsonl").read_text().splitlines()]
    assert rows and all(r["fallback"] == "rules" for r in rows)


# ---------------- outputs & evaluation ----------------
def test_outputs_written_and_marked_draft(failures, tmp_path):
    clusters, stats = triage(failures, engine="rules")
    write_outputs(clusters, stats, tmp_path, "t")
    tickets = list((tmp_path / "tickets").glob("*.md"))
    assert len(tickets) == stats["clusters"]
    assert all("DRAFT" in p.read_text() for p in tickets)


def test_score_perfect_prediction(failures):
    labels = load_labels(EVAL)
    clusters = []
    for rc in sorted({v["root_cause"] for v in labels.values()}):
        fs = [f for f in failures if labels[f.test_id]["root_cause"] == rc]
        cat = labels[fs[0].test_id]["category"]
        clusters.append(Cluster(rc, rc, fs, Verdict(cat, 0.9, "")))
    s = score(clusters, labels)
    assert s["accuracy"] == 1.0 and s["grouping"]["pairwise_f1"] == 1.0 and s["silent_errors"] == 0
