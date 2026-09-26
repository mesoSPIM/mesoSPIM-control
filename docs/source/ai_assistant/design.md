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
needs no polling rule. An acquisition still running after `WAIT_CAP_S` returns `still_running`,
and the model polls from there.

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
look right after a snap. A reply that called no tool is handed back once, and the tab says when a
turn sent nothing to the microscope.

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
