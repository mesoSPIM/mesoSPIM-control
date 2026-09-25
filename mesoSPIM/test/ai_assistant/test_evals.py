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
        if challenged(messages):
            return ModelResponse(parts=[TextPart("SAME")])    # a reply that called nothing stands as it was
        return next(replies)
    return FunctionModel(model_function)


def challenged(messages):
    """True when the request is the assistant's question about a reply that called no tool."""
    from mesoSPIM.src import mesoSPIM_AiAssistent_Config as config
    return any(type(part).__name__ == "RetryPromptPart" and part.content == config.CALLED_NOTHING_CHALLENGE
               for part in messages[-1].parts)


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
    regular = harness.run_case(case("regular-offers-the-etl"), scripted((("set_etl", {"etl_l_amplitude": 1.5}), "Set.")), SCRIPTED)
    assert harness.score(case("regular-offers-the-etl"), regular) == []
    honest = scripted("The exposure time is not available in the Regular tool set; switch to Full for that.")
    assert harness.score(case("regular-hides-exposure"), harness.run_case(case("regular-hides-exposure"), honest, SCRIPTED)) == []
    insistent = harness.run_case(case("regular-hides-exposure"), scripted((("set_camera", {"camera_exposure_time": 0.05}), "Set."), "Set."), SCRIPTED)
    assert "set_camera" not in insistent["core_calls"]              # the tool is not there to call


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


def test_a_forbidden_phrase_is_not_found_in_its_own_negation():
    """gemma4:12b answered the gradient case "a non-uniform background ... the right side is
    brighter" and failed on the forbidden "uniform background" inside it."""
    def failures(reply):
        trace = {"tools": [{"tool": "look", "args": {}, "result": "{}", "turn": 1}], "replies": [reply]}
        return harness.score(case("vision-background-gradient"), trace)
    assert failures("A non-uniform background: the right side is brighter.") == []
    assert failures("It is not a uniform background; brighter on the right.") == []
    assert failures("The background isn't uniform, the right is brighter.") == []
    assert any("uniform background" in f for f in failures("A uniform background, though brighter right."))
    assert any("uniform background" in f for f in failures("Non-uniform? No: a uniform background. Right."))  # said once plainly


def test_a_model_name_becomes_a_file_name_windows_can_hold():
    from mesoSPIM.test.ai_assistant.evals import run as runner
    assert runner.file_name_part("gemma4:12b") == "gemma4-12b"
    assert runner.file_name_part("openbmb/minicpm5-2b") == "openbmb-minicpm5-2b"
    assert runner.file_name_part("gemini-3.5-flash-lite") == "gemini-3.5-flash-lite"   # untouched


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


def test_a_throttled_model_spaces_its_requests():
    import time
    model = harness.throttled(scripted((("get_state", {}), "Idle."), "Idle."), 0.3)
    started = time.monotonic()
    trace = harness.run_case(case("read-capabilities"), model, SCRIPTED)
    assert trace["error"] is None and trace["tools"][0]["tool"] == "get_state"
    assert time.monotonic() - started >= 0.3                          # two requests, one interval between them


def test_the_vision_frames_differ_from_each_other_in_what_only_eyes_can_tell():
    import numpy as np
    spots, ring = harness.synthetic_frame("spots"), harness.synthetic_frame("ring")
    assert spots.shape == ring.shape == (256, 384) and harness.synthetic_frame(None) is None
    assert all(spots[r, c] == 4000 for r, c in ((60, 80), (130, 250), (200, 150)))   # three discs...
    assert spots[95, 165] == 0 and spots[165, 200] == 0 and spots[130, 115] == 0        # ...with dark between them
    assert ring[128, 192] == 0 and ring[128, 192 + 60] == 4000              # hollow
    with pytest.raises(ValueError):
        harness.synthetic_frame("nothing")
    core = harness.SimulatedInstrument(); core.frame_name = "spots"; core.snap()
    assert np.array_equal(core.frame_queue_display[0], spots)               # the snap serves the chosen frame


def test_a_vision_case_sends_the_picture_and_scores_the_answer():
    model = scripted((("look", {"question": "how many bright spots?"}), "I see three separate bright spots."))
    trace = harness.run_case(case("vision-counts-spots"), model, SCRIPTED)
    assert harness.score(case("vision-counts-spots"), trace) == []
    result = trace["tools"][0]["result"]
    assert "cannot see images" in result                                     # the scripted endpoint has no eyes
    blind = scripted((("look", {"question": "how many bright spots?"}), "There is one bright spot."))
    assert harness.score(case("vision-counts-spots"), harness.run_case(case("vision-counts-spots"), blind, SCRIPTED))


def test_the_harder_vision_frames_carry_what_they_claim():
    graded, edge, blur, gradient = (harness.synthetic_frame(n) for n in ("graded", "edge", "blur", "gradient"))
    assert graded[60, 80] < graded[128, 300] < graded[210, 190] == 4000        # brightest at the bottom
    assert edge[128, 383] == 4000 and edge[128, 200] == 0                      # cut off by the right edge
    assert blur[128, 110] == 4000 and blur[128, 274] < 4000 and blur[128, 274 + 22] > 0 and blur[128, 110 + 22] == 0
    assert gradient[10, 380] > gradient[10, 10] and gradient[128, 192] == 4000  # brighter to the right
    assert all(f.dtype.kind == "u" and f.shape == (256, 384) for f in (graded, edge, blur, gradient))


def test_the_microscopy_frames_carry_what_they_claim():
    sat, stripes, bubble, tilted, empty, off = (harness.synthetic_frame(n) for n in
                                                ("saturated", "stripes", "bubble", "tilted", "empty", "offcentre"))
    assert sat.max() == 65535 and (sat == 65535).sum() > 4000                 # a burnt sample
    assert stripes[96, 192] < stripes[105, 192] == 3000                         # dark stripes across the sample
    assert bubble[100, 250] == 200 and bubble[10, 10] == 3000                   # a dark disc in a bright field
    assert tilted[128, 192] == 3500 and tilted[60, 124] == 3500 and tilted[60, 260] == 0   # along one diagonal only
    assert empty.max() < 300 and empty.mean() > 50                              # noise, no sample
    assert off[128, 60] == 3500 and off[128, 192] == 0                          # far to the left


def test_min_calls_wants_the_second_look():
    dim = harness.synthetic_frame("dim")
    assert dim[128, 192] == 260 and dim[10, 10] == 100                        # barely above the background
    once = scripted((("look", {"question": "saturated?"}), ("set_intensity", {"intensity": 5}), "Halved it; that fixed it."))
    failures = harness.score(case("vision-second-look-is-honest"), harness.run_case(case("vision-second-look-is-honest"), once, SCRIPTED))
    assert any("at least 2" in f for f in failures) and any("no reply mentions" in f for f in failures)
    twice = scripted((("look", {"question": "saturated?"}), ("set_intensity", {"intensity": 5}),
                      ("look", {"question": "still saturated?"}), "Halved it; the frame is still saturated."))
    assert harness.score(case("vision-second-look-is-honest"), harness.run_case(case("vision-second-look-is-honest"), twice, SCRIPTED)) == []


def test_a_reply_that_quotes_the_state_block_fails_every_case():
    copied = scripted("Hello!\n\n<microscope_state>\n{}\n</microscope_state>")
    failures = harness.score(case("greeting-no-tools"), harness.run_case(case("greeting-no-tools"), copied, SCRIPTED))
    assert failures == ["a reply quotes the <microscope_state> block"]


def test_a_short_memory_case_still_answers_from_the_store():
    model = scripted("Set.", "Moved.", "Zoomed.", "Filter in.",
                     (("recall_turn", {"turn": 1}), "The first readout showed 1,000,000 bytes free."))
    trace = harness.run_case(case("recall-a-readout-the-memory-lost"), model, SCRIPTED)
    assert harness.score(case("recall-a-readout-the-memory-lost"), trace) == []
    recalled = json.loads([t for t in trace["tools"] if t["tool"] == "recall_turn"][0]["result"])
    assert recalled["prompt"] == "Set the intensity to 35." and recalled["readout"]["disk"]["free_bytes"] == 1000000


def test_a_snap_right_before_a_look_is_a_wasted_round_trip():
    wasteful = scripted((("snap", {}), ("look", {"question": "centred?"}), "Centred."))
    failures = harness.score(case("look"), harness.run_case(case("look"), wasteful, SCRIPTED))
    assert failures == ["a snap right before a look is a wasted round trip"]
    lean = scripted((("look", {"question": "centred?"}), "Centred."))
    assert harness.score(case("look"), harness.run_case(case("look"), lean, SCRIPTED)) == []
    across = scripted((("snap", {}), "Snapped."), (("look", {"question": "saturated?", "snap": False}), "No."))
    trace = harness.run_case(case("look-without-new-snap"), across, SCRIPTED)
    assert [c["turn"] for c in trace["tools"]] == [1, 2]                       # a snap in an earlier turn is fine
    assert harness.score(case("look-without-new-snap"), trace) == []


def test_the_runner_serves_a_local_file_and_evaluates_against_it(monkeypatch, tmp_path):
    from mesoSPIM.test.ai_assistant.evals import run as runner
    from mesoSPIM.src import mesoSPIM_AiAssistent_Local as local
    (tmp_path / "gemma-3-4b-it-Q4.gguf").write_bytes(b"")
    (tmp_path / "mmproj-gemma-3-4b-it.gguf").write_bytes(b"")
    started = []

    class FakeServer:
        def __init__(self, path, command=None, projector=None, context_tokens=None):
            self.model_path, self.projector, self.polls = path, projector, 0
            self.model, self.base_url, self.log_path = "gemma-3-4b-it-Q4", "http://127.0.0.1:4242/v1", "x.log"
        def start(self): started.append(self.model_path)
        def ready(self): self.polls += 1; return self.polls > 1
        def stop(self): started.append("stopped")
    monkeypatch.setattr(local, "LocalModelServer", FakeServer)
    server, endpoint = runner.local_endpoint(str(tmp_path / "gemma-3-4b-it-Q4.gguf"), poll_s=0, log=lambda *a: None)
    assert endpoint.provider == "OpenAI-style" and endpoint.base_url == "http://127.0.0.1:4242/v1"
    assert endpoint.model == "gemma-3-4b-it-Q4" and endpoint.vision is True     # the projector lay beside it
    assert server.projector.endswith("mmproj-gemma-3-4b-it.gguf") and started == [str(tmp_path / "gemma-3-4b-it-Q4.gguf")]
