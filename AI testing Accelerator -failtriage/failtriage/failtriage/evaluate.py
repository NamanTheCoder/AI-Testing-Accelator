"""Measure triage quality against a hand-labelled run.

Metrics
  * Category accuracy and macro-F1, per failed test (each test inherits its group's verdict)
  * Per-category precision / recall and a confusion matrix
  * Grouping quality: pairwise precision/recall of "same root cause" vs the labelled root_cause
  * Review load: issues a human must look at (groups) vs raw failures
  * Calibration: accuracy of verdicts the tool marks as confident vs those it flags for review
  * Wall-clock time and token usage
  * Optional: manual baseline from results/manual_timing.csv (seconds + label per test)
"""
from __future__ import annotations

import csv
import itertools
import json
from collections import Counter
from pathlib import Path

from .models import Category, Cluster

CATS = Category.values()


def load_labels(run_dir: Path) -> dict[str, dict]:
    with (run_dir / "labels.csv").open() as fh:
        return {r["test_id"]: r for r in csv.DictReader(fh)}


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def score(clusters: list[Cluster], labels: dict[str, dict]) -> dict:
    pred_cat: dict[str, str] = {}
    pred_cluster: dict[str, str] = {}
    review: dict[str, bool] = {}
    for c in clusters:
        for t in c.test_ids:
            pred_cat[t] = c.verdict.category
            pred_cluster[t] = c.cluster_id
            review[t] = c.verdict.needs_human_review
    tests = [t for t in labels if t in pred_cat]
    missing = [t for t in labels if t not in pred_cat]

    correct = sum(pred_cat[t] == labels[t]["category"] for t in tests)
    confusion = {a: {b: 0 for b in CATS} for a in CATS}
    for t in tests:
        confusion[labels[t]["category"]][pred_cat[t]] += 1
    per_class = {}
    for k in CATS:
        tp = confusion[k][k]
        fp = sum(confusion[o][k] for o in CATS if o != k)
        fn = sum(confusion[k][o] for o in CATS if o != k)
        p, r, f = _prf(tp, fp, fn)
        per_class[k] = {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3), "support": tp + fn}
    macro_f1 = sum(v["f1"] for v in per_class.values() if v["support"]) / max(
        1, sum(1 for v in per_class.values() if v["support"]))

    # pairwise grouping quality
    tp = fp = fn = 0
    for a, b in itertools.combinations(tests, 2):
        same_true = labels[a]["root_cause"] == labels[b]["root_cause"]
        same_pred = pred_cluster[a] == pred_cluster[b]
        tp += same_true and same_pred
        fp += same_pred and not same_true
        fn += same_true and not same_pred
    gp, gr, gf = _prf(tp, fp, fn)

    confident = [t for t in tests if not review[t]]
    flagged = [t for t in tests if review[t]]
    acc = lambda ts: (sum(pred_cat[t] == labels[t]["category"] for t in ts) / len(ts)) if ts else None

    errors = [{"test_id": t, "expected": labels[t]["category"], "predicted": pred_cat[t],
               "root_cause": labels[t]["root_cause"], "flagged_for_review": review[t],
               "note": labels[t]["note"]} for t in tests if pred_cat[t] != labels[t]["category"]]
    silent_errors = [e for e in errors if not e["flagged_for_review"]]

    return {
        "failures": len(tests),
        "missing_from_prediction": missing,
        "true_root_causes": len({labels[t]["root_cause"] for t in tests}),
        "predicted_groups": len({pred_cluster[t] for t in tests}),
        "accuracy": round(correct / len(tests), 3) if tests else 0.0,
        "macro_f1": round(macro_f1, 3),
        "per_class": per_class,
        "confusion": confusion,
        "grouping": {"pairwise_precision": round(gp, 3), "pairwise_recall": round(gr, 3), "pairwise_f1": round(gf, 3)},
        "auto_accepted_share": round(len(confident) / len(tests), 3) if tests else 0.0,
        "accuracy_when_confident": None if acc(confident) is None else round(acc(confident), 3),
        "accuracy_when_flagged": None if acc(flagged) is None else round(acc(flagged), 3),
        "errors": errors,
        "silent_errors": len(silent_errors),
    }


def load_manual(path: Path, labels: dict[str, dict]) -> dict | None:
    """results/manual_timing.csv: test_id,seconds,category (your own manual triage, timed)."""
    if not path.exists():
        return None
    rows = [r for r in csv.DictReader(path.open()) if r.get("seconds", "").strip()]
    if not rows:
        return None
    secs = [float(r["seconds"]) for r in rows]
    labelled = [r for r in rows if r.get("category") and r["test_id"] in labels]
    acc = (sum(r["category"].strip().upper() == labels[r["test_id"]]["category"] for r in labelled) / len(labelled)
           if labelled else None)
    return {"tests_timed": len(rows), "total_s": sum(secs), "per_test_s": sum(secs) / len(rows),
            "accuracy": None if acc is None else round(acc, 3)}


def render_markdown(results: dict[str, dict], manual: dict | None, n_failures: int) -> str:
    def pct(x):
        return "-" if x is None else f"{x*100:.0f}%"

    engines = list(results)
    hdr = "| Metric | " + (" Manual (timed) |" if manual else "") + " | ".join(engines) + " |"
    sep = "|---|" + ("---|" if manual else "") + "---|" * len(engines)
    rows = []

    def row(name, fn, manual_val="-"):
        cells = [fn(results[e]) for e in engines]
        rows.append(f"| {name} | " + (f"{manual_val} |" if manual else "") + " | ".join(cells) + " |")

    man_total = manual and manual["per_test_s"] * n_failures
    row("Time to triage the whole run",
        lambda r: f"{r['stats']['elapsed_s']:.1f} s",
        f"{man_total/60:.0f} min (extrapolated)" if manual else "-")
    row("Issues to look at (groups)",
        lambda r: f"{r['score']['predicted_groups']} (true: {r['score']['true_root_causes']})",
        f"{n_failures} (one per failure)" if manual else "-")
    row("Category accuracy (per test)", lambda r: pct(r["score"]["accuracy"]),
        pct(manual["accuracy"]) if manual else "-")
    row("Macro-F1", lambda r: f"{r['score']['macro_f1']:.2f}")
    row("Grouping pairwise F1", lambda r: f"{r['score']['grouping']['pairwise_f1']:.2f}")
    row("Auto-accepted (not flagged)", lambda r: pct(r["score"]["auto_accepted_share"]))
    row("Accuracy when confident", lambda r: pct(r["score"]["accuracy_when_confident"]))
    row("Wrong AND not flagged (silent errors)", lambda r: str(r["score"]["silent_errors"]))
    row("LLM tokens in/out", lambda r: (f"{r['stats']['usage']['input_tokens']}/{r['stats']['usage']['output_tokens']}"
                                        if r["stats"].get("usage") else "n/a"))

    out = [f"# Evaluation results ({n_failures} labelled failures)", "", hdr, sep, *rows, ""]
    for e in engines:
        s = results[e]["score"]
        out += [f"## {e}: per-category", "", "| Category | Precision | Recall | F1 | Support |", "|---|---|---|---|---|"]
        for k, v in s["per_class"].items():
            out.append(f"| {k} | {v['precision']:.2f} | {v['recall']:.2f} | {v['f1']:.2f} | {v['support']} |")
        out += ["", "Confusion matrix (rows = truth, cols = predicted):", "",
                "| truth \\ pred | " + " | ".join(CATS) + " |", "|---|" + "---|" * len(CATS)]
        for a in CATS:
            out.append(f"| {a} | " + " | ".join(str(s["confusion"][a][b]) for b in CATS) + " |")
        if s["errors"]:
            out += ["", "Misclassified tests:", "", "| Test | Truth | Predicted | Flagged? | Why it is hard |",
                    "|---|---|---|---|---|"]
            for err in s["errors"]:
                out.append(f"| `{err['test_id'].rsplit('.', 2)[-2]}.{err['test_id'].rsplit('.', 1)[-1]}` | "
                           f"{err['expected']} | {err['predicted']} | {'yes' if err['flagged_for_review'] else '**no**'} | "
                           f"{err['note']} |")
        out.append("")
    return "\n".join(out)


def save(results: dict, manual: dict | None, out_dir: Path, n_failures: int) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "eval_results.json").write_text(json.dumps({"engines": results, "manual": manual}, indent=2))
    md = out_dir / "EVAL_RESULTS.md"
    md.write_text(render_markdown(results, manual, n_failures))
    return md
