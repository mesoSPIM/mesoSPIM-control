"""Run the AI Assistant's behavioural evaluation against real models.

    python -m mesoSPIM.test.ai_assistant.evals.run --provider Gemini [--model NAME[,NAME...]] [--repeat N]
        [--profile Regular] [--only id,id] [--out runs/{date}-{model}.jsonl]
    python -m mesoSPIM.test.ai_assistant.evals.run --rescore runs/2026-09-17-gemini-3.5-flash-lite.jsonl
    python -m mesoSPIM.test.ai_assistant.evals.run --local ~/mesoSPIM/models/gemma-3-12b-it-Q4_K_M.gguf
    python -m mesoSPIM.test.ai_assistant.evals.run --provider OpenAI-style --base-url http://localhost:11434/v1 --model qwen3:8b

--local serves a GGUF file exactly as the tab's Local AI mode does (with its projector file when
one lies beside it, so the model can see) and evaluates against it; --base-url points the
OpenAI-style preset at a server already running (Ollama, llama-server, vLLM). The key comes from
the tab's environment variable for the provider (GEMINI_API_KEY, ...). Each
case is printed as it finishes; every trace is appended to the output file, whose name may carry
{date}, {provider} and {model}; several models run one after the other, each --repeat times, so
one command benchmarks a prompt across models and shows which cases are a coin flip. The exit
status is 1 when a case fails. --rescore re-applies the expectations to recorded traces without
calling a model, for a changed case file. scoreboard.py summarises run files."""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

from mesoSPIM.test.ai_assistant.evals import harness
from mesoSPIM.src import mesoSPIM_AiAssistent as ai
from mesoSPIM.src import mesoSPIM_AiAssistent_Config as config


def run_suite(cases, model, endpoint, profile, sink, repeat=1, pause=0.0, log=print, retries=2, retry_wait=None):
    """Run every case `repeat` times, appending each trace (with its score) to `sink`. Returns
    the (case, trace, failures) triples in order."""
    results = []
    for round_number in range(1, repeat + 1):
        for index, case in enumerate(cases):
            if results:
                time.sleep(pause)
            trace = harness.run_case(case, model, endpoint, profile, retries=retries, retry_wait=retry_wait)
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
    parser.add_argument("--base-url", default="", help="an OpenAI-style server already running, e.g. http://localhost:11434/v1")
    parser.add_argument("--local", default="", help="a .gguf file to serve with llama.cpp as the tab's Local AI mode does")
    parser.add_argument("--vision", action="store_true", help="with --base-url: the server's model can see images")
    parser.add_argument("--repeat", type=int, default=1, help="run every case this many times")
    parser.add_argument("--profile", default=config.DEFAULT_TOOL_PROFILE, choices=sorted(config.TOOL_PROFILES))
    parser.add_argument("--only", default="", help="comma-separated case ids")
    parser.add_argument("--cases", default=str(harness.CASES_FILE))
    parser.add_argument("--out", default="assistant-evals-{date}-{model}.jsonl",
                        help="trace file; {date}, {provider} and {model} are filled in")
    parser.add_argument("--rescore", default="", help="score these recorded traces instead of running")
    parser.add_argument("--pause", type=float, default=2.0, help="seconds between cases, for per-minute rate limits")
    parser.add_argument("--retries", type=int, default=2, help="retries of a case after a provider error")
    parser.add_argument("--retry-wait", type=float, default=harness.RETRY_WAIT_S,
                        help="seconds before a retry; a per-minute token cap needs a full minute")
    parser.add_argument("--request-interval", type=float, default=0.0,
                        help="seconds between the model's requests, within a case too, for a per-minute token cap")
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

    server = None
    if arguments.local:
        server, endpoint = local_endpoint(arguments.local)
        endpoints = [endpoint]
    else:
        endpoints = []
        for name in [m.strip() for m in arguments.model.split(",")]:
            endpoint = ai.Endpoint.from_preset(arguments.provider, name, base_url=arguments.base_url)
            if arguments.vision:
                endpoint = dataclasses.replace(endpoint, vision=True)
            if endpoint.needs_key and not endpoint.api_key:
                print(f"set {config.PROVIDERS[arguments.provider]['key_env']} first", file=sys.stderr)
                return 2
            endpoints.append(endpoint)
    results = []
    try:
        for endpoint in endpoints:
            out = arguments.out.format(date=dt.date.today().isoformat(), provider=endpoint.provider, model=endpoint.model)
            print(f"== {endpoint.provider} {endpoint.model} -> {out}")
            with open(out, "a", encoding="utf-8") as sink:
                model = ai.build_model(endpoint)
                if arguments.request_interval:
                    model = harness.throttled(model, arguments.request_interval)
                results += run_suite(cases, model, endpoint, arguments.profile, sink,
                                     repeat=arguments.repeat, pause=arguments.pause,
                                     retries=arguments.retries, retry_wait=arguments.retry_wait)
    finally:
        if server is not None:
            server.stop()
    return report(results)


def local_endpoint(path, timeout_s=None, poll_s=0.5, log=print):
    """Serve the GGUF at `path` as the tab does and wait until it answers. Returns the server (to
    stop afterwards) and the endpoint to evaluate; the model may see images when a projector file
    for its family lies beside it."""
    from mesoSPIM.src.mesoSPIM_AiAssistent_Local import LocalModelServer, projector_for
    folder, name = os.path.split(path)
    projector = projector_for(folder or ".", os.path.splitext(name)[0])
    server = LocalModelServer(path, projector=projector)
    server.start()
    log(f"== serving {name} on {server.base_url}" + (f" with {os.path.basename(projector)}" if projector else "") + " ...")
    deadline = time.monotonic() + (timeout_s or config.LOCAL_SERVER_TIMEOUT_S)
    while not server.ready():
        if time.monotonic() > deadline:
            server.stop()
            raise SystemExit(f"the model did not answer within {timeout_s or config.LOCAL_SERVER_TIMEOUT_S} s; see {server.log_path}")
        time.sleep(poll_s)
    endpoint = ai.Endpoint.from_preset("OpenAI-style", model=server.model, base_url=server.base_url)
    return server, dataclasses.replace(endpoint, vision=projector is not None)


if __name__ == "__main__":
    sys.exit(main())
