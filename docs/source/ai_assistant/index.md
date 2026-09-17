# AI Assistant

An optional chat tab that drives the microscope in natural language. A [Pydantic AI](https://ai.pydantic.dev)
agent turns the Remote Control commands into tools and dispatches them through the **same**
`Acceptor` as the TCP and MCP transports, so every action obeys the existing accept-validation,
movement limits and one-mutation gate. The tab is idle until the operator sends a message, and the
Assistant and a network transport are mutually exclusive — only one controller holds the session.

This builds on [Remote Control](../remote_control/index.md); read that first.

```{toctree}
:maxdepth: 1

design
integration
```

## Requirements

- `pydantic-ai`, declared as the optional extra `ai-assistant`: install with
  `pip install -e ".[ai-assistant]"`, or `pip install pydantic-ai` on its own. It is imported
  lazily, so the application starts and every other feature works without it; the tab reports the
  missing module when the operator sends a first message.
- An API key for the chosen provider, or any server that speaks the OpenAI API (Ollama, vLLM, LM Studio).

## Setting it up

The tab opens as a chat. The line under the input box, **Set up AI assistant**, expands to three
boxes, **Preferences**, **Language model** and **Vision model**, with one **Connect** under them,
and opens by itself when something needs the operator: nothing configured yet, a missing key, or
a local model that failed to start. Once the assistant is ready it folds back. Each model box
starts with a **Type** dropdown; the fields after it follow the choice.

**Language model, Cloud AI.** Choose a provider (Gemini, OpenAI, Anthropic, or **OpenAI-style**
for any server that speaks the OpenAI API, such as an Ollama or vLLM already running somewhere, or
a hosted gateway), keep or edit the prefilled model name, and type the API key into the masked
field. OpenAI-style also asks for the server's base URL, and there the key is optional: Ollama
wants none, a gateway or a hosted API wants its token. The key is kept in memory for this mesoSPIM
session only and is never written to the repository, the microscope config, or a log. An empty
field falls back to the provider's environment variable (`GEMINI_API_KEY`, `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`), so a key exported before starting mesoSPIM keeps working.

**Language model, Local AI.** One **Model** dropdown lists the `.gguf` files in the models folder
(`~/mesoSPIM/models`, or the `ai_assistant_models_folder` attribute of the microscope config;
**Models folder…** points it elsewhere for the session). Download a file from Hugging Face, drop
it in, choose it, Connect. Nothing leaves the machine and no key is needed. Behind Connect,
mesoSPIM serves the file itself with llama.cpp's OpenAI-compatible server (`pip install
llama-cpp-python`, or the `ai-assistant-local` extra) as a child process on a loopback port; the
Connect button reads "Starting…" while the model loads, then turns green with "Connected".
Connecting again, or closing mesoSPIM, stops the child. A server that fails to start is reported
with the path of its log. Use a GPU build of llama-cpp-python for anything above a few billion
parameters; the 4B to 12B instruction models are the realistic range on a microscope PC.

**Vision model.** The model that reads camera frames when the assistant looks. *Same as language
model* (the default) lets the language model read frames itself when it can; a text-only local
model then decides from the numbers alone. Choosing Cloud AI or Local AI here gives it eyes: the
same fields as above, and the frame goes to this model in a separate call with the question, so
the conversation itself never carries images. A local vision model needs its projector file
(`mmproj-…gguf`) in the models folder beside the model file; mesoSPIM picks the one whose name
matches and serves the two together. Whether a given local file can see depends on
llama-cpp-python supporting that model family's projector.

**Preferences** apply at once. **Tool set** chooses what the assistant may do: *Regular* (the
default) is for a user setting up a sample on a configured microscope: reads, stage and sample
moves, laser, intensity, filter, zoom, shutters, the camera exposure time, snap, live, and the
acquisition and time lapse commands. *Full* adds the machine: ETL, galvo, laser and camera timing,
the ETL calibration files, the alignment modes and the generic setting call. In Regular the other
commands are not offered to the model at all, so it cannot be talked into them. The start-up
choice can be fixed per microscope with the config attribute `ai_assistant_tools` ("Regular" or
"Full"). TCP and MCP always serve every command; this is the assistant only. **Memory** is how
many turns the model remembers. **Downsample image to** is the size of the frame handed to the
vision model (longer side, 1024 px by default): smaller is cheaper and faster, and enough for "is
it centred" or "is it saturated"; the numbers always come from the full frame.

**Connect** applies the three boxes; a first message sent without pressing it applies them as
typed. Building a cloud endpoint does not contact the provider, so a wrong key shows up as an
error on the first message. The models can be changed between turns and the transcript is kept.
The presets live in `mesoSPIM_AiAssistent_Config.py` as defaults only.

## Using it

Open the **AI Assistant** tab and type. Commands the agent runs stream live above each answer, so
the operator sees exactly which named calls were issued. **Cancel request** stops the assistant: no
further tool calls this turn, an open Run / Cancel question is cancelled, and the turn ends at the
model's next reply; what the assistant already started keeps running. **Stop microscope now** is
the main window's Stop: the same queued signals to Core (state idle aborts the running mode, the
time lapse is cancelled) plus the stage stop, sent straight from the tab with nothing of the
assistant in between, so it is as immediate as the button on the main window and works before the
assistant has ever connected. It cancels the assistant as well.

## Limitations

These are known and deliberate; read them before using the tab on an instrument with a sample
loaded.

- **Three stage moves are gated by the operator, in code.** `load_sample`, `unload_sample` and
  `preview_acquisition` cross the stage's range and can collide faster than anyone reacts, so they
  do not execute until the operator presses **Run** in the bar above the input; Cancel there,
  Cancel request or Stop microscope refuse, and the model is told so. Starting a run is not gated:
  the model is instructed to summarise and ask only when the state shows something off (empty
  list, missing folder, short disk, pending warning) and Stop microscope ends a run at any time. This holds whatever the model was told or talked into.
- **The model call has no timeout.** `WAIT_CAP_S` bounds the microscope leg only. If the endpoint
  stalls — a burst over a tokens-per-minute quota is the usual cause — the turn blocks until the
  HTTP layer gives up, and Cancel gates tool dispatch but cannot abort a request already in
  flight.
- **A commanded move smaller than `POSITION_TOLERANCE` completes without verifying motion.**
  Arrival is tested as `abs(observed - target) > tolerance`, so with the default 1.0 µm a 1 µm move
  from the current position is "already reached" on the first poll and is reported as a successful
  arrival.

## What has been verified

- `mesoSPIM/test/ai_assistant/` — 18 offline tests covering the completion wrapper, tool
  construction, the worker's turn/error/interrupt behaviour, the Acceptor lifecycle, and the tab's
  wiring, transport-busy refusal and single-flight input lock. They run without Qt or hardware,
  reusing the Remote Control substitute:

  ```
  pytest mesoSPIM/test/remote_control mesoSPIM/test/ai_assistant \
      --ignore=mesoSPIM/test/remote_control/test_real_pyqt_smoke.py \
      --ignore=mesoSPIM/test/remote_control/test_real_pyqt_transport_smoke.py
  ```

  245 passed, 10 skipped, in either collection order.
- A 14-case behavioural suite (`evals/` in the contribution repository) driving the real dispatcher
  over a fake Core, scored on which hardware call landed and what state resulted rather than on
  wording. It covers plain verbs, unit conversion, reads, vocabulary refusals, out-of-limits
  refusal, ambiguity, and prompt injection.
- End-to-end operation against the Windows DemoStage build.

Not yet verified on real hardware.
