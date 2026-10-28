"""failtriage CLI.

  python -m failtriage run  <run_dir> [--engine claude|rules] [--out out/]
  python -m failtriage eval <labelled_run_dir> [--engines rules,claude] [--out results/]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .evaluate import load_labels, load_manual, save, score
from .llm import DEFAULT_MODEL, ClaudeTriager
from .parser import parse_run
from .pipeline import triage, write_outputs


def _context(run_dir: Path) -> dict | None:
    p = run_dir / "context.json"
    return json.loads(p.read_text()) if p.exists() else None


def _require_key(engine: str) -> None:
    if engine == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set. Export it (see README) or use --engine rules for the offline mode.")


def cmd_run(a: argparse.Namespace) -> None:
    run_dir = Path(a.run_dir)
    _require_key(a.engine)
    failures = parse_run(run_dir)
    if not failures:
        print("No failures found. Nothing to triage.")
        return
    out = Path(a.out)
    triager = ClaudeTriager(model=a.model, cache_dir=None if a.no_cache else out / ".cache") \
        if a.engine == "claude" else None
    clusters, stats = triage(failures, engine=a.engine, run_context=_context(run_dir),
                             triager=triager, audit_path=out / "audit.jsonl")
    write_outputs(clusters, stats, out, title=run_dir.name)
    print((out / "triage_report.md").read_text())
    print(f"Wrote {out}/triage_report.md, {out}/triage_result.json, {out}/tickets/, {out}/audit.jsonl")


def cmd_eval(a: argparse.Namespace) -> None:
    run_dir = Path(a.run_dir)
    out = Path(a.out)
    labels = load_labels(run_dir)
    failures = parse_run(run_dir)
    results = {}
    for engine in a.engines.split(","):
        engine = engine.strip()
        if engine == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
            print("Skipping claude engine: ANTHROPIC_API_KEY not set.")
            continue
        triager = ClaudeTriager(model=a.model, cache_dir=None if a.no_cache else out / ".cache") \
            if engine == "claude" else None
        clusters, stats = triage(failures, engine=engine, run_context=_context(run_dir), triager=triager,
                                 audit_path=out / f"audit_{engine}.jsonl")
        name = f"claude ({a.model})" if engine == "claude" else "rules baseline"
        results[name] = {"stats": stats, "score": score(clusters, labels)}
        write_outputs(clusters, stats, out / f"triage_{engine}", title=f"{run_dir.name} [{engine}]")
    manual = load_manual(Path(a.manual), labels)
    md = save(results, manual, out, n_failures=len(labels))
    print(md.read_text())
    print(f"Wrote {md} and {out}/eval_results.json")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="failtriage", description="AI triage for automated test failures")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="Triage one test run (directory of JUnit/TestNG XML reports)")
    r.add_argument("run_dir")
    r.add_argument("--engine", choices=["claude", "rules"], default="claude")
    r.add_argument("--model", default=DEFAULT_MODEL)
    r.add_argument("--out", default="out")
    r.add_argument("--no-cache", action="store_true", help="Always call the API (ignore cached verdicts)")
    r.set_defaults(func=cmd_run)

    e = sub.add_parser("eval", help="Score engines against a labelled run (labels.csv)")
    e.add_argument("run_dir")
    e.add_argument("--engines", default="rules,claude")
    e.add_argument("--model", default=DEFAULT_MODEL)
    e.add_argument("--out", default="results")
    e.add_argument("--manual", default="results/manual_timing.csv")
    e.add_argument("--no-cache", action="store_true")
    e.set_defaults(func=cmd_eval)

    a = p.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
