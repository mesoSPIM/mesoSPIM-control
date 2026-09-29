"""A scoreboard over recorded evaluation runs: one row per model, pass rates per category, the
cases that pass only sometimes, and how long the model took.

    python -m mesoSPIM.test.ai_assistant.evals.scoreboard runs/*.jsonl [--write runs/SCOREBOARD.md]

A run file holds one trace per case and repeat (run.py). Two runs of the same model in different
files are pooled, so repeats can be collected on different days. Turns that failed on the
provider's side (a rate limit, an outage) count as failed runs: the operator at the microscope
would have waited for nothing too; the column shows how many there were."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def load_traces(paths):
    traces = []
    for path in paths:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                traces.append(json.loads(line))
    return traces


def summarise(traces):
    """Per model: runs, passes, per-category (runs, passes), flaky case ids, provider errors,
    runs another model answered (the fallback rolled in), median seconds. Traces without a model
    name are pooled under "?"."""
    board = {}
    for trace in traces:
        model = trace.get("model") or "?"
        row = board.setdefault(model, {"runs": 0, "passes": 0, "categories": defaultdict(lambda: [0, 0]),
                                       "by_case": defaultdict(list), "errors": 0, "fallback": 0, "seconds": []})
        passed = not trace.get("failures")
        row["runs"] += 1
        row["passes"] += passed
        category = row["categories"][trace.get("category") or "?"]
        category[0] += 1
        category[1] += passed
        row["by_case"][trace["id"]].append(passed)
        row["errors"] += bool(trace.get("error"))
        row["fallback"] += any(name != model for name in trace.get("served") or [])
        row["seconds"].append(float(trace.get("seconds") or 0))
    for row in board.values():
        row["flaky"] = sorted(case for case, outcomes in row["by_case"].items() if len(set(outcomes)) > 1)
        row["always_failing"] = sorted(case for case, outcomes in row["by_case"].items() if not any(outcomes))
        row["median_seconds"] = statistics.median(row["seconds"]) if row["seconds"] else 0.0
    return board


def _rate(passes, runs):
    return f"{100 * passes / runs:.0f}%" if runs else "-"


def render(board):
    """The scoreboard as Markdown: an overview table, a per-category table, then the cases that
    deserve a look per model."""
    models = sorted(board, key=lambda m: (-board[m]["passes"] / max(board[m]["runs"], 1), m))
    categories = sorted({c for row in board.values() for c in row["categories"]})
    lines = ["| model | runs | pass | provider errors | fallback answered | median s | flaky | always failing |",
             "|---|---|---|---|---|---|---|---|"]
    for model in models:
        row = board[model]
        lines.append(f"| {model} | {row['runs']} | {_rate(row['passes'], row['runs'])} | {row['errors']} | {row['fallback']} | "
                     f"{row['median_seconds']:.1f} | {len(row['flaky'])} | {len(row['always_failing'])} |")
    lines += ["", "| category | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
    for category in categories:
        cells = [_rate(*reversed(board[m]["categories"].get(category, [0, 0]))) for m in models]
        lines.append(f"| {category} | " + " | ".join(cells) + " |")
    for model in models:
        row = board[model]
        if row["flaky"] or row["always_failing"]:
            lines += ["", f"**{model}**"]
            if row["always_failing"]:
                lines.append("- always failing: " + ", ".join(row["always_failing"]))
            if row["flaky"]:
                lines.append("- pass only sometimes: " + ", ".join(row["flaky"]))
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="+", help="trace files written by run.py")
    parser.add_argument("--write", default="", help="also write the Markdown here")
    arguments = parser.parse_args(argv)
    text = render(summarise(load_traces(arguments.runs)))
    print(text, end="")
    if arguments.write:
        Path(arguments.write).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
