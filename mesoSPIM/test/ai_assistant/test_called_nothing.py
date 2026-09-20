"""A reply at the end of a turn that called no tool goes back to the model once. gemma4:e4b
answered "Stop the time lapse." with "I have stopped the time lapse." and no call, three times in
three; whether it did so turned on the wording of unrelated lines of the manual."""
import threading

import pytest

from mesoSPIM.src import mesoSPIM_AiAssistent as ai
from mesoSPIM.test.ai_assistant.evals import harness
from mesoSPIM.test.ai_assistant.test_evals import SCRIPTED, challenged

pytest.importorskip("pydantic_ai")


def model_that(answers_challenge_with, first="I have stopped the time lapse.", then="The time lapse is stopped."):
    """A model that claims an action without a call, and answers the challenge as given: a tool
    call (name, args) or a text. Records every request it got."""
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
    from pydantic_ai.models.function import FunctionModel
    requests = []

    def model_function(messages, info):
        requests.append(messages)
        if challenged(messages):
            if isinstance(answers_challenge_with, tuple):
                return ModelResponse(parts=[ToolCallPart(tool_name=answers_challenge_with[0], args=answers_challenge_with[1])])
            return ModelResponse(parts=[TextPart(answers_challenge_with)])
        called = any(type(p).__name__ == "ToolReturnPart" for p in messages[-1].parts)
        return ModelResponse(parts=[TextPart(then if called else first)])
    return FunctionModel(model_function), requests


def run(model, *prompts, **case):
    return harness.run_case({"id": "called-nothing", "prompts": list(prompts), **case}, model, SCRIPTED)


def test_a_model_that_claimed_a_stop_gets_to_make_it():
    model, requests = model_that(("time_lapse_stop", {}))
    trace = run(model, "Stop the time lapse.", setup={"timelapse_active": True})
    assert [t["tool"] for t in trace["tools"]] == ["time_lapse_stop"] and '"stopped": true' in trace["tools"][0]["result"]
    assert trace["replies"] == ["The time lapse is stopped."]          # the reply after the call, not the claim
    assert len(requests) == 3                                           # the claim, the challenge, the report


def test_a_reply_that_stands_reaches_the_operator_word_for_word():
    """Asked to repeat itself a small model writes something shorter and worse, so the answer to
    the challenge is thrown away and the first reply kept."""
    model, requests = model_that("SAME", first="Hello! The instrument is idle; what shall we image?")
    trace = run(model, "Hi there!")
    assert trace["replies"] == ["Hello! The instrument is idle; what shall we image?"] and trace["tools"] == []
    assert len(requests) == 2
    model, _ = model_that("I am ready.", first="Which axis, and how far in micrometres?")
    assert run(model, "Move it a bit.")["replies"] == ["Which axis, and how far in micrometres?"]


def test_a_turn_that_called_a_tool_is_not_asked():
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
    from pydantic_ai.models.function import FunctionModel
    requests = []

    def model_function(messages, info):
        requests.append(messages)
        done = any(type(p).__name__ == "ToolReturnPart" for p in messages[-1].parts)
        return ModelResponse(parts=[TextPart("Closed.") if done else ToolCallPart(tool_name="close_shutters", args={})])
    trace = run(FunctionModel(model_function), "Close the shutters.")
    assert trace["replies"] == ["Closed."] and len(requests) == 2 and not any(challenged(r) for r in requests)


def test_the_memory_of_an_earlier_turn_ends_on_the_reply_not_on_the_answer_to_the_challenge():
    model, requests = model_that("SAME", first="Hello!")
    run(model, "Hi there!", "And again.")
    second_turn = requests[2]                                           # what the model was sent for "And again."
    texts = [part.content for message in second_turn for part in message.parts if type(part).__name__ == "TextPart"]
    assert texts == ["Hello!"] and not any(ai._is_challenge(message) for message in second_turn)


def test_cancel_and_an_empty_challenge_switch_it_off(monkeypatch):
    cancel = threading.Event()
    cancel.set()
    model, requests = model_that("SAME")
    agent = ai.build_agent(harness.SimulatedAcceptor(harness.SimulatedInstrument()), cancel, model=model)
    assert agent.run_sync("Stop.").output == "I have stopped the time lapse." and len(requests) == 1
    monkeypatch.setattr(ai.config, "CALLED_NOTHING_CHALLENGE", "")
    model, requests = model_that("SAME")
    agent = ai.build_agent(harness.SimulatedAcceptor(harness.SimulatedInstrument()), threading.Event(), model=model)
    assert agent.run_sync("Stop.").output == "I have stopped the time lapse." and len(requests) == 1
