"""Group failures that share a root cause, so 40 red tests caused by one dead
database become one ticket, not 40.

The signature is deliberately simple and explainable (no embeddings): reviewers
in a bank need to see *why* two failures were grouped.
"""
from __future__ import annotations

import hashlib
import re
from collections import OrderedDict

from .masker import mask
from .models import Cluster, Failure

FRAMEWORK_PREFIXES = (
    "java.", "javax.", "jdk.", "sun.", "kotlin.", "org.junit", "junit.", "org.testng", "org.openqa",
    "io.restassured", "org.apache", "org.hamcrest", "org.assertj", "com.microsoft.playwright",
    "org.springframework", "io.cucumber", "net.bytebuddy", "com.sun.",
    "_pytest", "pytest", "pluggy", "playwright", "selenium", "requests", "urllib3", "httpx",
    "site-packages", "unittest",
)
ASSERTION_TYPES = ("assertionerror", "assertionfailederror", "comparisonfailure", "assert")
CODE_DEFECT_TYPES = ("nullpointerexception", "illegalstateexception", "illegalargumentexception",
                     "classcastexception", "indexoutofbounds", "typeerror", "keyerror", "attributeerror")

_JAVA_FRAME = re.compile(r"at\s+([\w.$<>]+)\(([^)]*)\)")
_PY_FRAME = re.compile(r'File "([^"]+)", line \d+, in (\w+)')
_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
_HEX = re.compile(r"\b0x[0-9a-f]+\b|\b[0-9a-f]{12,}\b", re.I)
_TS = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?")
_NUM = re.compile(r"\d+(?:\.\d+)?")
_WS = re.compile(r"\s+")


def normalise_message(msg: str) -> str:
    s = msg.strip().splitlines()[0] if msg.strip() else ""
    s = _TS.sub("<TS>", s)
    s = _UUID.sub("<UUID>", s)
    s = _HEX.sub("<HEX>", s)
    s = _NUM.sub("<N>", s)
    s = _WS.sub(" ", s)
    return s[:200]


def app_frames(stack: str, limit: int = 2) -> list[str]:
    """First frames that belong to *our* code (test or app), skipping framework/library frames."""
    frames: list[str] = []
    for m in _JAVA_FRAME.finditer(stack):
        name = m.group(1)
        if not name.startswith(FRAMEWORK_PREFIXES):
            frames.append(re.sub(r":\d+", "", f"{name}({m.group(2)})"))
    if not frames:
        # Python tracebacks list the innermost frame LAST; reverse so [0] is where it raised.
        for m in reversed(list(_PY_FRAME.finditer(stack))):
            path, fn = m.group(1), m.group(2)
            if not any(p in path for p in FRAMEWORK_PREFIXES):
                frames.append(f"{path}:{fn}")
    return frames[:limit]


_HTTP_STATUS = re.compile(r"expected status code <(\d{3})> but was <(\d{3})>", re.I)
_LOG_ERROR = re.compile(r"^.*\b(ERROR|FATAL|Exception|refused|unavailable)\b.*$", re.I | re.M)


def log_fingerprint(log: str) -> str:
    """First error-looking log line, normalised (timestamps/ids/numbers stripped)."""
    m = _LOG_ERROR.search(mask(log or "").text)
    if not m:
        return ""
    line = re.sub(r"^\S*\d{2}:\d{2}:\d{2}\S*\s*", "", m.group(0))  # drop leading timestamp
    return normalise_message(line)[:120]


def signature(f: Failure) -> str:
    exc = (f.exception_type or "").rsplit(".", 1)[-1]
    exc_l = exc.lower()
    msg = normalise_message(mask(f.message or f.stacktrace).text)
    parts = [exc or "UnknownError", msg]
    http = _HTTP_STATUS.search(f.message or "")
    if http:
        # API status-code mismatches: same status pair + same server-side error => same root cause,
        # regardless of which test hit it.
        parts = [f"HTTP {http.group(1)}->{http.group(2)}", log_fingerprint(f.log_excerpt)]
    elif any(t in exc_l for t in ASSERTION_TYPES):
        # Assertion failures are almost always test-specific: keep them apart per test.
        parts.append(f.test_id)
    elif any(t in exc_l for t in CODE_DEFECT_TYPES):
        # Code defects: group by where in OUR code it blew up.
        parts.extend(app_frames(f.stacktrace, limit=1))
    return " | ".join(parts)


def cluster(failures: list[Failure]) -> list[Cluster]:
    groups: "OrderedDict[str, list[Failure]]" = OrderedDict()
    for f in failures:
        groups.setdefault(signature(f), []).append(f)
    clusters = []
    for sig, items in groups.items():
        cid = "C-" + hashlib.sha1(sig.encode()).hexdigest()[:8]
        clusters.append(Cluster(cluster_id=cid, signature=sig, failures=items))
    # biggest blast radius first
    clusters.sort(key=lambda c: len(c.failures), reverse=True)
    return clusters
