"""The held-out cases (evals/cases_holdout.json): a variant of each of the 110 cases with other
wording, numbers, axes, settings and frames, written without running a model on it, to tell a
change that made the assistant better from one that fitted it to cases.json. Here only the file
is tested: it is sound, it mirrors cases.json, and what it expects can be reached on the
simulated instrument by a scripted model that does the right thing."""
import pytest

from mesoSPIM.src.mesoSPIM_RemoteControl_Frame import frame_stats
from mesoSPIM.test.ai_assistant.evals import harness
from mesoSPIM.test.ai_assistant.test_evals import SCRIPTED, scripted

pytest.importorskip("pydantic_ai")

HOLDOUT = harness.CASES_FILE.with_name("cases_holdout.json")


def held(case_id):
    return next(c for c in harness.load_cases(HOLDOUT) if c["id"] == "h-" + case_id)


def test_the_held_out_file_is_sound_and_mirrors_the_cases():
    cases, originals = harness.load_cases(HOLDOUT), harness.load_cases()
    assert harness.check_cases(cases) == []
    assert [c["category"] for c in cases] == [c["category"] for c in originals]      # case for case
    assert not {c["id"] for c in cases} & {c["id"] for c in originals}
    prompts = lambda cs: {p for c in cs for p in harness.prompts_of(c)}
    assert len(prompts(cases) & prompts(originals)) <= 3                              # other words, not a copy
    for c in cases:
        harness.synthetic_frame((c.get("setup") or {}).get("frame"))                 # every frame exists


def test_the_held_out_frames_say_what_their_cases_assume():
    def stats(name):
        return frame_stats(harness.synthetic_frame(name))
    assert stats("saturated2")["saturated_fraction"] > 0.03                          # "a few percent": lower the intensity
    assert stats("good")["saturated_fraction"] == 0 and stats("good")["max"] > 0.1 * stats("good")["full_scale"]
    assert stats("dim2")["max"] < 0.1 * stats("dim2")["full_scale"]                 # underexposed by the manual's rule
    assert stats("empty2")["max"] < 0.1 * stats("empty2")["full_scale"]


IDEAL = {   # the right calls for the cases whose outcome is a state of the instrument
    "move-relative-mm": [("move_relative", {"deltas": {"y": 250}})],
    "move-absolute-um": [("move_absolute", {"targets": {"z": 1200}})],
    "move-absolute-mm": [("move_absolute", {"targets": {"x": -3000}})],
    "move-two-axes": [("move_absolute", {"targets": {"y": 2000, "x": -1500}})],
    "move-focus": [("move_relative", {"deltas": {"f": -300}})],
    "move-theta": [("move_relative", {"deltas": {"theta": 45}})],
    "move-half-mm": [("move_relative", {"deltas": {"z": 250}})],
    "move-negative-mm": [("move_absolute", {"targets": {"y": -4200}})],
    "move-scientific": [("move_absolute", {"targets": {"z": 2500}})],
    "center-sample": [("center_sample", {})],
    "laser": [("set_laser", {"laser": "561 nm"})],
    "intensity": [("set_intensity", {"intensity": 45})],
    "zoom": [("set_zoom", {"zoom": "2x"})],
    "filter-valid": [("set_filter", {"filter": "515LP"})],
    "shutter-side": [("set_shutterconfig", {"shutterconfig": "Both"})],
    "shutters-close": [("close_shutters", {})],
    "exposure-ms": [("set_camera", {"camera_exposure_time": 0.02})],
    "exposure-microseconds": [("set_camera", {"camera_exposure_time": 0.002})],
    "intensity-zero": [("set_intensity", {"intensity": 0})],
    "busy-live-setting-allowed": [("set_intensity", {"intensity": 65})],
    "live-start": [("start_live", {})],
    "stop": [("stop", {})],
    "time-lapse-stop": [("time_lapse_stop", {})],
    "load-sample-confirmed": [("load_sample", {})],
    "unload-sample-confirmed": [("unload_sample", {})],
    "french-move": [("move_absolute", {"targets": {"y": 8000}})],
}


@pytest.mark.parametrize("case_id", sorted(IDEAL))
def test_a_model_that_does_the_right_thing_passes_the_held_out_case(case_id):
    case = held(case_id)
    trace = harness.run_case(case, scripted((*IDEAL[case_id], "Done.")), SCRIPTED)
    assert harness.score(case, trace) == [], trace["tools"]


@pytest.mark.parametrize("case_id, calls", [
    ("move-out-of-limits", [("move_absolute", {"targets": {"x": -400000}})]),
    ("no-retry-same-value", [("move_absolute", {"targets": {"z": -800000}})]),
    ("move-relative-out-of-limits", [("move_relative", {"deltas": {"z": -30000}})]),
])
def test_the_held_out_limits_are_really_outside_the_range(case_id, calls):
    case = held(case_id)
    trace = harness.run_case(case, scripted((*calls, "That is outside the allowed range, so I cannot do it.")), SCRIPTED)
    assert "outside the allowed range" in trace["tools"][0]["result"] and harness.score(case, trace) == []
