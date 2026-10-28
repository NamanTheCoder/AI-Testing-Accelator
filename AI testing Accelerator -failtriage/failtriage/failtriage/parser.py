"""Parse JUnit-style XML (Surefire, Gradle, PyTest --junitxml, Playwright junit reporter)
and TestNG testng-results.xml into Failure objects."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .models import Failure

LOG_TAIL_CHARS = 2000


def _tail(text: str | None, n: int = LOG_TAIL_CHARS) -> str:
    text = (text or "").strip()
    return text[-n:]


def _first_line_exception(stack: str) -> str:
    first = stack.strip().splitlines()[0] if stack.strip() else ""
    head = first.split(":", 1)[0].strip()
    return head if "." in head or head.endswith(("Error", "Exception")) else ""


def parse_junit(path: Path) -> list[Failure]:
    tree = ET.parse(path)
    root = tree.getroot()
    suites = [root] if root.tag == "testsuite" else root.iter("testsuite")
    failures: list[Failure] = []
    for suite in suites:
        suite_name = suite.get("name", "")
        for case in suite.iter("testcase"):
            node = case.find("failure")
            if node is None:
                node = case.find("error")
            if node is None:
                continue
            stack = (node.text or "").strip()
            classname = case.get("classname", suite_name)
            failures.append(
                Failure(
                    test_id=f"{classname}.{case.get('name', '?')}",
                    message=(node.get("message") or "").strip(),
                    exception_type=(node.get("type") or _first_line_exception(stack)).strip(),
                    stacktrace=stack,
                    log_excerpt=_tail(
                        (case.findtext("system-out") or "") + "\n" + (case.findtext("system-err") or "")
                    ),
                    duration_s=float(case.get("time", 0) or 0),
                    suite=suite_name,
                    source_file=path.name,
                )
            )
    return failures


def parse_testng(path: Path) -> list[Failure]:
    root = ET.parse(path).getroot()
    failures: list[Failure] = []
    for suite in root.iter("suite"):
        suite_name = suite.get("name", "")
        for cls in suite.iter("class"):
            for m in cls.iter("test-method"):
                if m.get("status") != "FAIL" or m.get("is-config") == "true":
                    continue
                exc = m.find("exception")
                exc_type = exc.get("class", "") if exc is not None else ""
                message = (exc.findtext("message") or "").strip() if exc is not None else ""
                stack = (exc.findtext("full-stacktrace") or "").strip() if exc is not None else ""
                out = "\n".join((ln.text or "") for ln in m.iter("line"))
                failures.append(
                    Failure(
                        test_id=f"{cls.get('name')}.{m.get('name')}",
                        message=message,
                        exception_type=exc_type,
                        stacktrace=stack,
                        log_excerpt=_tail(out),
                        duration_s=float(m.get("duration-ms", 0) or 0) / 1000,
                        suite=suite_name,
                        source_file=path.name,
                    )
                )
    return failures


def parse_file(path: Path) -> list[Failure]:
    root_tag = ET.parse(path).getroot().tag
    if root_tag == "testng-results":
        return parse_testng(path)
    if root_tag in ("testsuite", "testsuites"):
        return parse_junit(path)
    raise ValueError(f"Unrecognised report format in {path} (root <{root_tag}>)")


def load_history(run_dir: Path) -> dict[str, str]:
    """Optional history.json: {"<test_id>": "PPFPP..."} (oldest -> newest, excluding this run)."""
    p = run_dir / "history.json"
    return json.loads(p.read_text()) if p.exists() else {}


def parse_run(run_dir: Path) -> list[Failure]:
    """Parse every *.xml report under a run directory and attach pass/fail history."""
    run_dir = Path(run_dir)
    history = load_history(run_dir)
    failures: list[Failure] = []
    for xml in sorted(run_dir.rglob("*.xml")):
        failures.extend(parse_file(xml))
    for f in failures:
        f.history = history.get(f.test_id, "")
    return failures
