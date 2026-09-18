"""Run the AI Assistant's behavioural evaluation against real models.

    python -m mesoSPIM.test.ai_assistant.evals.run --provider Gemini [--model NAME[,NAME...]] [--repeat N]
        [--profile Regular] [--only id,id] [--out runs/{date}-{model}.jsonl]
    python -m mesoSPIM.test.ai_assistant.evals.run --rescore runs/2026-09-17-gemini-3.5-flash-lite.jsonl

The key comes from the tab's environment variable for the provider (GEMINI_API_KEY, ...). Each
case is printed as it finishes; every trace is appended to the output file, whose name may carry
{date}, {provider} and {model}; several models run one after the other, each --repeat times, so
one command benchmarks a prompt across models and shows which cases are a coin flip. The exit
status is 1 when a case fails. --rescore re-applies the expectations to recorded traces without
calling a model, for a changed case file. scoreboard.py summarises run files."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

from mesoSPIM.test.ai_assistant.evals import harness
from mesoSPIM.src import mesoSPIM_AiAssistent as ai
from mesoSPIM.src import mesoSPIM_AiAssistent_Config as config


def run_suite(cases, model, endpoint, profile, sink, repeat=1, pause=0.0, log=print):
    """Run every case `repeat` times, appending each trace (with its score) to `sink`. Returns
    the (case, trace, failures) triples in order."""
    results = []
    for round_number in range(1, repeat + 1):
        for index, case in enumerate(cases):
            if results:
                time.sleep(pause)
            trace = harness.run_case(case, model, endpoint, profile)
            failures = harness.score(case, trace)
            trace["failures"] = failures
            trace["provider"], trace["model"], trace["repeat"] = endpoint.provider, endpoint.model, round_number
            sink.write(json.dumps(trace, ensure_ascii=False, default=str) + "\n")
            sink.flush()
            results.append((case, trace, failures))
            log(f"{'PASS' if not failures else 'FAIL'}  {case['id']:<32} {trace['seconds']:>6.1f}s  {' | '.join(failures)}")
    return results


def report(results, log=print):
    failed = [r for r in results if r[2]]
    log(f"\n{len(results) - len(failed)} of {len(results)} runs pass")
    for case, trace, failures in failed:
        log(f"  {case['id']} ({trace.get('model')}, run {trace.get('repeat', 1)}): {'; '.join(failures)}")
        for tool in trace["tools"]:
            log(f"      {tool['tool']}({json.dumps(tool['args'])}) -> {str(tool['result'])[:120]}")
        for reply in trace.get("replies") or []:
            log(f"      reply: {reply[:200]}")
    return min(len(failed), 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", default=config.DEFAULT_PROVIDER, choices=sorted(config.PROVIDERS))
    parser.add_argument("--model", default="", help="model name(s), comma-separated; the preset's when omitted")
    parser.add_argument("--repeat", type=int, default=1, help="run every case this many times")
    parser.add_argument("--profile", default=config.DEFAULT_TOOL_PROFILE, choices=sorted(config.TOOL_PROFILES))
    parser.add_argument("--only", default="", help="comma-separated case ids")
    parser.add_argument("--cases", default=str(harness.CASES_FILE))
    parser.add_argument("--out", default="assistant-evals-{date}-{model}.jsonl",
                        help="trace file; {date}, {provider} and {model} are filled in")
    parser.add_argument("--rescore", default="", help="score these recorded traces instead of running")
    parser.add_argument("--pause", type=float, default=2.0, help="seconds between cases, for per-minute rate limits")
    arguments = parser.parse_args(argv)

    cases = harness.load_cases(arguments.cases)
    problems = harness.check_cases(cases)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 2
    by_id = {case["id"]: case for case in cases}
    if arguments.only:
        cases = [by_id[case_id] for case_id in arguments.only.split(",")]

    if arguments.rescore:
        traces = [json.loads(line) for line in Path(arguments.rescore).read_text(encoding="utf-8").splitlines() if line]
        results = [(by_id[t["id"]], t, harness.score(by_id[t["id"]], t)) for t in traces if t["id"] in by_id]
        return report(results)

    results = []
    for name in [m.strip() for m in arguments.model.split(",")]:
        endpoint = ai.Endpoint.from_preset(arguments.provider, name)
        if endpoint.needs_key and not endpoint.api_key:
            print(f"set {config.PROVIDERS[arguments.provider]['key_env']} first", file=sys.stderr)
            return 2
        out = arguments.out.format(date=dt.date.today().isoformat(), provider=endpoint.provider, model=endpoint.model)
        print(f"== {endpoint.provider} {endpoint.model} -> {out}")
        with open(out, "a", encoding="utf-8") as sink:
            results += run_suite(cases, ai.build_model(endpoint), endpoint, arguments.profile, sink,
                                 repeat=arguments.repeat, pause=arguments.pause)
    return report(results)


if __name__ == "__main__":
    sys.exit(main())
