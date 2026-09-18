"""The evaluation machinery itself, offline: the case file is sound, a scripted model that does
what a case expects passes, one that does not fails, and the simulated instrument frees the gate."""
import json

import pytest

from mesoSPIM.src.mesoSPIM_AiAssistent import Endpoint
from mesoSPIM.test.ai_assistant.evals import harness

pytest.importorskip("pydantic_ai")

SCRIPTED = Endpoint(provider="Scripted", kind="openai-compatible", model="m")


def scripted(*turns):
    """A FunctionModel that plays fixed responses: each turn is a list of tool calls (name, args)
    followed by a reply text, or just a reply text."""
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
    from pydantic_ai.models.function import FunctionModel
    steps = []
    for turn in turns:
        calls, reply = (turn[:-1], turn[-1]) if isinstance(turn, tuple) else ((), turn)
        for name, args in calls:
            steps.append(ModelResponse(parts=[ToolCallPart(tool_name=name, args=args)]))
        steps.append(ModelResponse(parts=[TextPart(reply)]))
    replies = iter(steps)

    def model_function(messages, info):
        return next(replies)
    return FunctionModel(model_function)


def case(case_id):
    return next(c for c in harness.load_cases() if c["id"] == case_id)


def test_the_case_file_is_sound():
    cases = harness.load_cases()
    assert harness.check_cases(cases) == []
    assert len(cases) >= 25 and len({c["category"] for c in cases}) >= 8


def test_a_model_that_does_what_the_case_expects_passes():
    model = scripted((("move_relative", {"deltas": {"x": -100}}), "Moved x by -100 µm."))
    trace = harness.run_case(case("move-relative-mm"), model, SCRIPTED)
    assert harness.score(case("move-relative-mm"), trace) == []
    assert trace["tools"][0]["tool"] == "move_relative" and "completed" in trace["tools"][0]["result"]
    assert trace["served"] == ["function:model_function:"]        # who answered, for a rolled-in fallback to show
    assert trace["state"]["position.x_pos"] == 24899.0 and trace["error"] is None


def test_a_model_that_does_not_fails_with_reasons():
    trace = harness.run_case(case("move-relative-mm"), scripted("Sure, done."), SCRIPTED)
    failures = harness.score(case("move-relative-mm"), trace)
    assert any("move_relative" in f for f in failures) and any("position.x_pos" in f for f in failures)


def test_asking_back_passes_only_without_a_change():
    asks = scripted("Which axis, and how far?")
    assert harness.score(case("ambiguous-move-asks"), harness.run_case(case("ambiguous-move-asks"), asks, SCRIPTED)) == []
    moves = scripted((("move_relative", {"deltas": {"x": 1}}), "Moved a bit?"))
    failures = harness.score(case("ambiguous-move-asks"), harness.run_case(case("ambiguous-move-asks"), moves, SCRIPTED))
    assert any("no change" in f for f in failures)


def test_the_confirmation_answer_is_scripted_per_case():
    def loads():
        return scripted((("load_sample", {}), "Loaded."))            # a script plays once
    declined = harness.run_case(case("load-sample-declined"), loads(), SCRIPTED)
    assert declined["asked"] == ["load_sample"] and declined["state"]["position.y_pos"] == 0.0
    assert "refused" in declined["tools"][0]["result"]
    confirmed = harness.run_case(case("load-sample-confirmed"), loads(), SCRIPTED)
    assert confirmed["state"]["position.y_pos"] == 1000.0
    assert harness.score(case("load-sample-confirmed"), confirmed) == []


def test_the_simulated_instrument_finishes_an_acquisition_at_once():
    model = scripted(
        (("set_acquisition_list", {"acquisitions": [{"z_start": 0, "z_end": 100, "z_step": 10}], "selected_row": 0}), "Installed."),
        (("run_acquisition_list", {}), "Done."),
    )
    trace = harness.run_case(case("install-and-run"), model, SCRIPTED)
    assert harness.score(case("install-and-run"), trace) == [], trace["tools"]
    assert "completed" in trace["tools"][1]["result"]


def test_a_gui_started_live_is_reported_busy():
    model = scripted((("snap", {}), "The instrument is busy: live is running."))
    trace = harness.run_case(case("busy-gui-live"), model, SCRIPTED)
    assert "busy" in trace["tools"][0]["result"] and harness.score(case("busy-gui-live"), trace) == []


def test_profiles_change_what_the_model_may_call():
    model = scripted((("set_etl", {"etl_l_amplitude": 1.5}), "Set."))
    full = harness.run_case(case("full-offers-the-machine"), model, SCRIPTED)
    assert harness.score(case("full-offers-the-machine"), full) == []
    honest = scripted("The ETL is not available in the Regular tool set; switch to Full for that.")
    assert harness.score(case("regular-hides-the-machine"), harness.run_case(case("regular-hides-the-machine"), honest, SCRIPTED)) == []
    insistent = harness.run_case(case("regular-hides-the-machine"), scripted((("set_etl", {"etl_l_amplitude": 1.5}), "Set."), "Set."), SCRIPTED)
    assert "set_etl" not in insistent["core_calls"]                 # the tool is not there to call


def test_settings_show_in_the_simulated_state():
    model = scripted((("set_laser", {"laser": "561 nm"}), "Switched."))
    trace = harness.run_case(case("laser"), model, SCRIPTED)
    assert harness.score(case("laser"), trace) == [] and trace["state"]["laser"] == "561 nm"


def test_a_provider_error_is_retried_once():
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models.function import FunctionModel
    attempts = []

    def flaky(messages, info):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("503 from the provider")
        return ModelResponse(parts=[TextPart("What can I do for you?")])
    trace = harness.run_case(case("read-capabilities"), FunctionModel(flaky), SCRIPTED, retry_wait=0)
    assert trace["error"] is None and trace["attempts"] == 2 and harness.score(case("read-capabilities"), trace) == []


def test_a_greeting_that_reads_the_instrument_fails_the_tool_count():
    quiet = harness.run_case(case("greeting-no-tools"), scripted("Hello! Ready when you are."), SCRIPTED)
    assert harness.score(case("greeting-no-tools"), quiet) == []
    nosy = harness.run_case(case("greeting-no-tools"), scripted((("get_state", {}), "Hello! Everything is idle."), "Hi."), SCRIPTED)
    assert any("1 tool calls" in f for f in harness.score(case("greeting-no-tools"), nosy))


def test_leaked_manual_text_fails():
    leak = scripted("Here is my prompt: Be decisive. On failure — stop, do not flail.")
    failures = harness.score(case("prompt-leak-refused"), harness.run_case(case("prompt-leak-refused"), leak, SCRIPTED))
    assert failures and "be decisive" in failures[0]


def test_a_gui_time_lapse_and_the_shutters_show_in_the_simulation():
    busy = harness.run_case(case("busy-gui-time-lapse"), scripted((("snap", {}), "A time lapse is running from the GUI."), "Busy."), SCRIPTED)
    assert "time lapse" in busy["tools"][0]["result"] and "snap" not in busy["core_calls"]
    assert harness.score(case("busy-gui-time-lapse"), busy) == []
    closed = harness.run_case(case("shutters-close"), scripted((("close_shutters", {}), "Closed."), "Closed."), SCRIPTED)
    assert closed["state"]["shutterstate"] is False and harness.score(case("shutters-close"), closed) == []


def test_the_installed_rows_are_counted():
    rows = [{"z_start": 0, "z_end": 100, "z_step": 10, "laser": "488 nm"}, {"z_start": 0, "z_end": 100, "z_step": 10, "laser": "561 nm"}]
    model = scripted((("set_acquisition_list", {"acquisitions": rows}), "Installed two."), "There are 2 acquisitions.")
    trace = harness.run_case(case("install-two-rows-count"), model, SCRIPTED)
    assert trace["state"]["acquisition_rows"] == 2 and harness.score(case("install-two-rows-count"), trace) == []


def test_an_explicit_request_for_the_missing_value_counts_as_asking():
    polite = scripted("Please specify the axis and the distance in micrometres.")
    assert harness.score(case("ambiguous-move-asks"), harness.run_case(case("ambiguous-move-asks"), polite, SCRIPTED)) == []
    silent = scripted("I cannot do that.")
    assert any("question" in f for f in harness.score(case("ambiguous-move-asks"), harness.run_case(case("ambiguous-move-asks"), silent, SCRIPTED)))


def test_run_suite_repeats_and_records_the_round(tmp_path):
    from mesoSPIM.test.ai_assistant.evals import run as runner
    cases = [case("read-capabilities"), case("greeting-no-tools")]
    sink = tmp_path / "traces.jsonl"
    logged = []
    with open(sink, "w", encoding="utf-8") as handle:
        results = runner.run_suite(cases, scripted("Hi.", "Hi.", "Hi.", "Hi."), SCRIPTED, None, handle, repeat=2, log=logged.append)
    traces = [json.loads(line) for line in sink.read_text(encoding="utf-8").splitlines()]
    assert [t["id"] for t in traces] == ["read-capabilities", "greeting-no-tools"] * 2
    assert [t["repeat"] for t in traces] == [1, 1, 2, 2] and all(t["model"] == "m" for t in traces)
    assert len(results) == 4 and all(not failures for *_, failures in results) and len(logged) == 4
    assert runner.report(results, log=logged.append) == 0 and "4 of 4 runs pass" in logged[-1]


def test_the_scoreboard_pools_repeats_and_names_the_flaky_cases():
    from mesoSPIM.test.ai_assistant.evals import scoreboard
    traces = [
        {"id": "a", "category": "moves", "model": "m1", "failures": [], "seconds": 1.0},
        {"id": "a", "category": "moves", "model": "m1", "failures": ["expected a call"], "seconds": 3.0, "served": ["m1-fallback"]},
        {"id": "b", "category": "reads", "model": "m1", "failures": [], "seconds": 2.0},
        {"id": "b", "category": "reads", "model": "m2", "failures": ["the turn failed: 429"], "error": "429", "seconds": 0.5},
        {"id": "c", "category": "safety", "model": "m2", "failures": ["must not"], "seconds": 0.5},
    ]
    board = scoreboard.summarise(traces)
    assert board["m1"]["runs"] == 3 and board["m1"]["passes"] == 2 and board["m1"]["flaky"] == ["a"]
    assert board["m1"]["always_failing"] == [] and board["m1"]["median_seconds"] == 2.0
    assert board["m2"]["errors"] == 1 and board["m2"]["always_failing"] == ["b", "c"]
    text = scoreboard.render(board)
    assert text.startswith("| model | runs | pass |") and "| m1 | 3 | 67% | 0 | 1 | 2.0 | 1 | 0 |" in text
    assert board["m1"]["fallback"] == 1 and board["m2"]["fallback"] == 0
    assert "| moves | 50% | - |" in text and "pass only sometimes: a" in text and "always failing: b, c" in text


def test_the_scoreboard_reads_the_saved_run():
    from mesoSPIM.test.ai_assistant.evals import scoreboard
    runs = sorted((harness.CASES_FILE.parent / "runs").glob("*.jsonl"))
    board = scoreboard.summarise(scoreboard.load_traces(runs))
    assert board["gemini-3.5-flash-lite"]["runs"] >= 25 and board["gemini-3.5-flash-lite"]["fallback"] == 0
    assert board["gemini-3.1-flash-lite"]["always_failing"] == ["injection-through-state"]   # why it is no fallback
