# Design

The decisions behind the AI Assistant and why each was made. [Integration](integration.md) says
where the code sits; the [manual](index.md) says how the tab behaves.

## One more caller of the Acceptor

The assistant is an in-process sibling of the TCP and MCP transports: its tools call
`Acceptor.dispatch()`, so every action passes the same validation, movement limits and
one-mutation gate, and the assistant adds no command logic and no safety logic of its own. Going
through the loopback MCP server instead would have spared the lifecycle code, but put the chat
outside the application. One controller holds the session at a time: the assistant refuses to
start while a transport runs, and a transport refuses while the assistant holds the Acceptor.

## Tools from the command registry

Each offered command becomes one tool with the command's own JSON schema, the one MCP's
`tools/list` serves, so the tool list is never maintained by hand. The tools skip pydantic's own
validation of a call: the command's `accept()` stays the one place a call is refused, with one
error vocabulary, and the refusal goes back to the model as data.

A tool returns when the instrument is done, not when the command is admitted: the wrapper polls
`get_progress` until the operation ends, so one tool call is one finished action and the model
needs no polling rule. Two kinds of command return earlier, on purpose. A mode that runs until
stopped (live, the visual and alignment modes) returns once it runs, and the dispatcher then
treats it as the operator's live view: the operation that started it is complete, settings and
moves pass as they do from the GUI, a take-over is refused with a message that names this
session, and `stop_activity` ends it (`RUNS_UNTIL_STOPPED`). A run that ends by itself but takes
minutes to hours (the acquisition commands and the time lapse) returns once it is under way, so
the turn ends and the input line is free for "stop"; the run holds the gate against everything
but a stop until it ends (`RUNS_ON_ITS_OWN`). Anything else still running after `WAIT_CAP_S`
returns `still_running`, and the model polls from there.

The eyes (`VisionSession`) are the vision model's own conversation, kept by the worker for the
session. `look` sends the frame into it as a turn (time, the readout keys a picture depends on,
the numbers, the image, the question), `ask_eyes` sends a question alone, and after each turn
`detach_old_frames` strips the image from every frame turn but the last `VISION_FRAMES_KEPT`,
keeping the text, so the cost per look stays about one frame with a provider that caches the
prefix. The main model still never carries an image. The evaluation shows the eyes a different
frame each turn through a case's `frames` list.

The scheduler is the tab's, not the model's: `Scheduler` holds named schedules, the two tools
add and cancel them from the worker thread, and a one-second Qt timer on the GUI thread pops the
first due one and submits its instruction as a turn (`SCHEDULED_TURN`), never while a turn runs.
The readout carries the clock and the schedules on every turn, so the model has a clock without
having to keep time.

## What the model is offered

The **Regular** tool set leaves out what a user setting up a sample has no business with: the
camera settings, the galvos, laser timing, the alignment modes, the generic setting call, and the
ETL's delay and ramps (`set_etl` takes the voltages only). The model is not offered them at all
and is told they exist in the Full set, so it cannot be talked into them and does not stand another
command in for one. **Full** offers every command.

## Rules in code, where the prompt was not enough

The evaluation found small models reading a rule and doing otherwise, so the rules that matter
most are held in code. `load_sample`, `unload_sample` and `preview_acquisition` cross the stage's
range and wait for the operator's **Run**. `TurnGuard` keeps, for one turn, what a refusal ruled
out: no other target on an axis refused for its limit, no stop to clear a GUI-busy instrument
without **Run**, no third intensity or exposure change without **Run**, no second exposure for a
look right after a snap, and no value the operator did not give: a number or option in their
words, or arithmetic they named on a readout value, passes; "brighter" sent as 20 % waits for
**Run**. A reply that called no tool is handed back once, and the tab says when a turn sent
nothing to the microscope.

## The voice

The model answers in the register the manual is written in. An earlier manual gave orders
("do not", "stop", capitals, "one or two sentences") and the assistant answered in kind: a fact,
then silence, about "the operator" in the third person. The manual now speaks to the operator as
*you*, gives each rule its reason, and on a refusal asks for the next step ("propose one fix as a
question") instead of stopping. The same prompts under both manuals scored the same on the
evaluation; the replies got shorter, not longer, and stopped sounding like a machine. Two things
to watch when softening a rule: a model told to ask may ask where it was allowed to correct (a
listed option spelled differently), and may "help" by clamping an out-of-range value to the
limit; both exceptions are named in the manual.

## Context

Every operator message carries the instrument's readout in a `<microscope_state>` block, so the
model acts on current values without reading them first; the block is data, escaped so that no
text in it can close it. Older turns are compacted to a one-line readout and shortened tool
results before each request, and every turn stays whole in a session store the model can search
and recall, so a long session costs little and loses nothing.

## Failures

A model that is rate-limited or unavailable is an error the operator sees; there is no
whole-turn retry, which would re-run every tool call the first attempt made. The Gemini preset
names no fallback model: in the evaluation the stand-in obeyed a note planted in the readout that
the chosen model never did. When another model answers anyway, the tab says so and the trace
records it.
