"""failtriage CLI.

  python -m failtriage run  <run_dir> [--engine groq|claude|rules] [--out out/]
  python -m failtriage eval <labelled_run_dir> [--engines rules,groq] [--out results/]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .evaluate import load_labels, load_manual, save, score
from .llm import (
    DEFAULT_CLAUDE_MODEL,
    DEFAULT_ENGINE,
    DEFAULT_GROQ_MODEL,
    ClaudeTriager,
    GroqTriager,
)
from .parser import parse_run
from .pipeline import triage, write_outputs


def _context(run_dir: Path) -> dict | None:
    p = run_dir / "context.json"
    return json.loads(p.read_text()) if p.exists() else None


def _require_key(engine: str) -> None:
    if engine == "groq" and not os.environ.get("GROQ_API_KEY"):
        sys.exit("GROQ_API_KEY is not set. Set it in .env or export GROQ_API_KEY=..., or use --engine rules for offline mode.")
    if engine == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set. Export it (see README) or use --engine rules for offline mode.")


def cmd_run(a: argparse.Namespace) -> None:
    run_dir = Path(a.run_dir)
    _require_key(a.engine)
    failures = parse_run(run_dir)
    if not failures:
        print("No failures found. Nothing to triage.")
        return
    out = Path(a.out)
    cache_dir = None if a.no_cache else out / ".cache"
    if a.engine == "groq":
        triager = GroqTriager(model=a.model or DEFAULT_GROQ_MODEL, cache_dir=cache_dir)
    elif a.engine == "claude":
        triager = ClaudeTriager(model=a.model or DEFAULT_CLAUDE_MODEL, cache_dir=cache_dir)
    else:
        triager = None
    clusters, stats = triage(failures, engine=a.engine, run_context=_context(run_dir),
                             triager=triager, audit_path=out / "audit.jsonl", limit=a.limit)
    write_outputs(clusters, stats, out, title=run_dir.name)
    print((out / "triage_report.md").read_text())
    print(f"Wrote {out}/triage_report.md, {out}/triage_result.json, {out}/tickets/, {out}/audit.jsonl")


def cmd_eval(a: argparse.Namespace) -> None:
    run_dir = Path(a.run_dir)
    out = Path(a.out)
    labels = load_labels(run_dir)
    failures = parse_run(run_dir)
    results = {}
    cache_dir = None if a.no_cache else out / ".cache"
    for engine in a.engines.split(","):
        engine = engine.strip()
        if engine == "groq" and not os.environ.get("GROQ_API_KEY"):
            print("Skipping groq engine: GROQ_API_KEY not set.")
            continue
        if engine == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
            print("Skipping claude engine: ANTHROPIC_API_KEY not set.")
            continue
        if engine == "groq":
            model = a.model or DEFAULT_GROQ_MODEL
            triager = GroqTriager(model=model, cache_dir=cache_dir)
            name = f"groq ({model})"
        elif engine == "claude":
            model = a.model or DEFAULT_CLAUDE_MODEL
            triager = ClaudeTriager(model=model, cache_dir=cache_dir)
            name = f"claude ({model})"
        else:
            triager = None
            name = "rules baseline"
        clusters, stats = triage(failures, engine=engine, run_context=_context(run_dir), triager=triager,
                                 audit_path=out / f"audit_{engine}.jsonl")
        results[name] = {"stats": stats, "score": score(clusters, labels)}
        write_outputs(clusters, stats, out / f"triage_{engine}", title=f"{run_dir.name} [{engine}]")
    manual = load_manual(Path(a.manual), labels)
    md = save(results, manual, out, n_failures=len(labels))
    print(md.read_text())
    print(f"Wrote {md} and {out}/eval_results.json")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="failtriage", description="AI triage for automated test failures")
    sub = p.add_subparsers(dest="cmd", required=True)

    default_engines = "rules,groq" if os.environ.get("GROQ_API_KEY") else ("rules,claude" if os.environ.get("ANTHROPIC_API_KEY") else "rules")

    r = sub.add_parser("run", help="Triage one test run (directory of JUnit/TestNG XML reports)")
    r.add_argument("run_dir")
    r.add_argument("--engine", choices=["groq", "claude", "rules"], default=DEFAULT_ENGINE)
    r.add_argument("--model", default=None)
    r.add_argument("--out", default="out")
    r.add_argument("--limit", type=int, default=None, help="Triage only the top N failure groups")
    r.add_argument("--no-cache", action="store_true", help="Always call the API (ignore cached verdicts)")
    r.set_defaults(func=cmd_run)

    e = sub.add_parser("eval", help="Score engines against a labelled run (labels.csv)")
    e.add_argument("run_dir")
    e.add_argument("--engines", default=default_engines)
    e.add_argument("--model", default=None)
    e.add_argument("--out", default="results")
    e.add_argument("--manual", default="results/manual_timing.csv")
    e.add_argument("--no-cache", action="store_true")
    e.set_defaults(func=cmd_eval)

    a = p.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
