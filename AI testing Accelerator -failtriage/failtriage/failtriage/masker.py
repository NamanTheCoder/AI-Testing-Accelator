"""Redact sensitive data from test failure text BEFORE anything is sent to an LLM.

Test logs in a bank routinely contain card numbers, account numbers, customer
names, emails, tokens and passwords (from test data, request/response dumps,
connection strings). This module is deliberately conservative: it would rather
over-redact than leak.

It is pattern-based, so it is a control, not a guarantee. See LIMITS_AND_RISKS.md.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field


def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


# key=value / "key": "value" style secrets and personal fields
_SENSITIVE_KEYS = (
    r"password|passwd|pwd|secret|api[_-]?key|client[_-]?secret|access[_-]?token|refresh[_-]?token|"
    r"authorization|customer[_-]?name|first[_-]?name|last[_-]?name|full[_-]?name|account[_-]?holder|"
    r"dob|date[_-]?of[_-]?birth|ssn|tfn|pan[_-]?number|aadhaar|passport|mobile|phone"
)
_KV_RE = re.compile(
    rf"""(?ix)
    (?P<key>["']?(?:{_SENSITIVE_KEYS})["']?\s*[:=]\s*)
    (?P<q>["']?)
    (?P<val>[^"',;&\s}}\]]+(?:\s[A-Z][a-z]+)?)
    (?P=q)
    """
)
_ACCOUNT_RE = re.compile(
    r"(?i)(?P<key>\b(?:account|acct|a/c|acc)(?:[_ -]?(?:no|num|number|id))?\b[\"']?\s*[:=#]?\s*[\"']?)"
    r"(?P<val>\d{6,18})"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}(?:\s?[A-Z0-9]{1,3})?\b")
_PAN_CANDIDATE_RE = re.compile(r"(?<![\d.])(?:\d[ -]?){12,18}\d(?![\d.])")
_BSB_RE = re.compile(r"(?i)\bBSB\b\s*[:=]?\s*\d{3}-?\d{3}")
_URL_CRED_RE = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)([^:/\s@]+):([^@\s/]+)@")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_LONG_DIGITS_RE = re.compile(r"(?<![\d.])\d{9,}(?![\d.])")


@dataclass
class MaskResult:
    text: str
    counts: Counter = field(default_factory=Counter)
    residual_warnings: list[str] = field(default_factory=list)


def mask(text: str) -> MaskResult:
    if not text:
        return MaskResult(text="")
    counts: Counter = Counter()

    def sub(pattern: re.Pattern, repl, label: str, s: str) -> str:
        def _r(m: re.Match) -> str:
            out = repl(m) if callable(repl) else repl
            if out != m.group(0):
                counts[label] += 1
            return out
        return pattern.sub(_r, s)

    s = text
    s = sub(_URL_CRED_RE, lambda m: f"{m.group(1)}<USER>:<SECRET>@", "url_credential", s)
    s = sub(_BEARER_RE, "Bearer <TOKEN>", "bearer_token", s)
    s = sub(_JWT_RE, "<JWT>", "jwt", s)
    s = sub(_KV_RE, lambda m: f"{m.group('key')}{m.group('q')}<REDACTED>{m.group('q')}", "sensitive_field", s)
    s = sub(_EMAIL_RE, "<EMAIL>", "email", s)
    s = sub(_IBAN_RE, "<IBAN>", "iban", s)
    s = sub(_BSB_RE, "BSB <BSB>", "bsb", s)
    s = sub(_ACCOUNT_RE, lambda m: f"{m.group('key')}<ACCOUNT>", "account_number", s)

    def _pan(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            return "<PAN>"
        return m.group(0)
    s = sub(_PAN_CANDIDATE_RE, _pan, "card_number", s)
    s = sub(_IPV4_RE, "<IP>", "ip_address", s)

    # Anything still looking like a long identifier is flagged (not silently passed).
    residual = [f"unlabelled long number: {d[:3]}…({len(d)} digits)" for d in _LONG_DIGITS_RE.findall(s)]
    return MaskResult(text=s, counts=counts, residual_warnings=residual)


def mask_failure_fields(fields: dict[str, str]) -> tuple[dict[str, str], Counter, list[str]]:
    """Mask several named text fields; returns masked fields, total counts and warnings."""
    total: Counter = Counter()
    warnings: list[str] = []
    out: dict[str, str] = {}
    for k, v in fields.items():
        r = mask(v)
        out[k] = r.text
        total.update(r.counts)
        warnings.extend(f"{k}: {w}" for w in r.residual_warnings)
    return out, total, warnings
