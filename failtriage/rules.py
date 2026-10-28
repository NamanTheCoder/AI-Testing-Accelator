"""Rule-based triage: the 'keyword tagger' many teams already have.

Used two ways:
  1. As a BASELINE in the evaluation, so the LLM is compared against something
     smarter than nothing.
  2. As the OFFLINE engine (--engine rules) when no API key is available or when
     data must not leave the machine.
"""
from __future__ import annotations

import re

from .clusterer import app_frames
from .models import Category, Cluster, Verdict

ENV_PATTERNS = [
    r"connection refused", r"connectexception", r"unknownhost", r"no route to host",
    r"\b50[234]\b", r"service unavailable", r"bad gateway", r"gateway time-?out",
    r"sslhandshake", r"certificate", r"could not acquire.*connection", r"too many connections",
    r"no space left", r"quota", r"session not created", r"chrome not reachable",
    r"selenium grid", r"grid status", r"no nodes support", r"econnreset", r"socket hang up", r"read timed out", r"connect timed out",
    r"test data .*not (found|available)", r"no (eligible|available) test (account|data)",
    r"rate limit", r"\b429\b", r"vault", r"kafka.*unavailable", r"mq.*unavailable",
]
TEST_BUG_PATTERNS = [
    r"nosuchelement", r"invalidselector", r"elementnotinteractable",
    r"element click intercepted", r"strict mode violation", r"locator\.", r"unable to locate element",
    r"stale ?element", r"no such element", r"invalid xpath",
]
FLAKY_PATTERNS = [r"timeoutexception", r"timed? ?out after", r"waiting for", r"intermittent"]
PRODUCT_PATTERNS = [r"\b500\b", r"internal server error", r"expected .* but (was|found)", r"assert"]


def _hit(patterns: list[str], text: str) -> str | None:
    for p in patterns:
        if re.search(p, text, re.I):
            return p
    return None


def flips(history: str) -> int:
    h = history.replace(" ", "")
    return sum(1 for a, b in zip(h, h[1:]) if a != b)


def classify_cluster(c: Cluster) -> Verdict:
    f = c.representative
    text = " ".join([f.exception_type, f.message, f.stacktrace[:1500], f.log_excerpt[-800:]])
    hist = f.history

    if hist and "F" in hist and "P" in hist and flips(hist) >= 3:
        return Verdict(Category.FLAKY.value, 0.6, f"History '{hist}' flips {flips(hist)} times",
                       "qa:automation", [f"history={hist}"], engine="rules")
    if p := _hit(ENV_PATTERNS, text):
        return Verdict(Category.ENVIRONMENT.value, 0.7, f"Matched environment pattern /{p}/",
                       "platform/devops", [p], engine="rules")
    if p := _hit(TEST_BUG_PATTERNS, text):
        return Verdict(Category.TEST_BUG.value, 0.65, f"Matched locator/test pattern /{p}/",
                       "qa:automation", [p], engine="rules")
    exc = f.exception_type.lower()
    if "nullpointer" in exc or "typeerror" in exc or "attributeerror" in exc:
        frames = app_frames(f.stacktrace, 1)
        in_test = bool(frames) and re.search(r"(test|page|steps|fixture|conftest)", frames[0], re.I)
        cat = Category.TEST_BUG if in_test else Category.PRODUCT_BUG
        return Verdict(cat.value, 0.55, f"Null/type error at {frames[0] if frames else '?'}",
                       "qa:automation" if in_test else "dev", frames, engine="rules")
    if p := _hit(FLAKY_PATTERNS, text):
        return Verdict(Category.FLAKY.value, 0.5, f"Matched timing pattern /{p}/",
                       "qa:automation", [p], engine="rules")
    if p := _hit(PRODUCT_PATTERNS, text):
        return Verdict(Category.PRODUCT_BUG.value, 0.55, f"Matched product pattern /{p}/",
                       "dev", [p], engine="rules")
    return Verdict(Category.PRODUCT_BUG.value, 0.3, "No rule matched; defaulting to product bug",
                   "dev", [], needs_human_review=True, engine="rules")
