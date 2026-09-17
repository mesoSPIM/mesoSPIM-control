"""Run the AI Assistant's behavioural evaluation against a real model.

    python -m mesoSPIM.test.ai_assistant.evals.run --provider Gemini [--model NAME] [--profile Regular]
        [--only id,id] [--out traces.jsonl]
    python -m mesoSPIM.test.ai_assistant.evals.run --rescore traces.jsonl

The key comes from the tab's environment variable for the provider (GEMINI_API_KEY, ...). Each
case is printed as it finishes; every trace is appended to the output file; the exit status is
the number of failing cases. --rescore re-applies the expectations to recorded traces without
calling a model, for a changed case file."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mesoSPIM.test.ai_assistant.evals import harness
from mesoSPIM.src import mesoSPIM_AiAssistent as ai
from mesoSPIM.src import mesoSPIM_AiAssistent_Config as config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", default=config.DEFAULT_PROVIDER, choices=sorted(config.PROVIDERS))
    parser.add_argument("--model", default="", help="model name; the preset's when omitted")
    parser.add_argument("--profile", default=config.DEFAULT_TOOL_PROFILE, choices=sorted(config.TOOL_PROFILES))
    parser.add_argument("--only", default="", help="comma-separated case ids")
    parser.add_argument("--cases", default=str(harness.CASES_FILE))
    parser.add_argument("--out", default="assistant-evals.jsonl")
    parser.add_argument("--rescore", default="", help="score these recorded traces instead of running")
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
    else:
        endpoint = ai.Endpoint.from_preset(arguments.provider, arguments.model)
        if endpoint.needs_key and not endpoint.api_key:
            print(f"set {config.PROVIDERS[arguments.provider]['key_env']} first", file=sys.stderr)
            return 2
        model = ai.build_model(endpoint)
        results = []
        with open(arguments.out, "a", encoding="utf-8") as sink:
            for case in cases:
                trace = harness.run_case(case, model, endpoint, arguments.profile)
                failures = harness.score(case, trace)
                trace["failures"] = failures
                trace["provider"], trace["model"] = endpoint.provider, endpoint.model
                sink.write(json.dumps(trace, ensure_ascii=False, default=str) + "\n")
                results.append((case, trace, failures))
                print(f"{'PASS' if not failures else 'FAIL'}  {case['id']:<32} {trace['seconds']:>6.1f}s  "
                      f"{' | '.join(failures)}")

    failed = [r for r in results if r[2]]
    print(f"\n{len(results) - len(failed)} of {len(results)} cases pass")
    for case, trace, failures in failed:
        print(f"  {case['id']}: {'; '.join(failures)}")
        for tool in trace["tools"]:
            print(f"      {tool['tool']}({json.dumps(tool['args'])}) -> {str(tool['result'])[:120]}")
        for reply in trace.get("replies") or []:
            print(f"      reply: {reply[:200]}")
    return min(len(failed), 1)


if __name__ == "__main__":
    sys.exit(main())
