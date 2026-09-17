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
- An API key for the chosen provider, or a local OpenAI-compatible server.

## Setting it up

The tab opens as a chat. The line under the input box, **Set up AI assistant**, expands to the
setup rows, and opens by itself when something needs the operator: nothing configured yet, a
missing key, or a local model that failed to start. Once the assistant is ready it folds back.

**Cloud.** Choose a provider (Gemini, OpenAI, Anthropic, or an OpenAI-compatible server such as
Ollama or vLLM already running somewhere, given by its base URL), keep or edit the prefilled model
name, and type the API key into the masked field. The key is kept in memory for this mesoSPIM
session only and is never written to the repository, the microscope config, or a log. An empty
field falls back to the provider's environment variable (`GEMINI_API_KEY`, `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`), so a key exported before starting mesoSPIM keeps working.

**Local.** One **Model** dropdown lists the `.gguf` files in the models folder (`~/mesoSPIM/models`,
or the `ai_assistant_models_folder` attribute of the microscope config; **Models folder…** points
it elsewhere for the session). Download a file from Hugging Face, drop it in, choose it, Connect.
Nothing leaves the machine and no key is needed. Behind Connect, mesoSPIM serves the file itself
with llama.cpp's OpenAI-compatible server (`pip install llama-cpp-python`, or the
`ai-assistant-local` extra) as a child process on a loopback port; the status reads "starting…"
while the model loads, then "ready on 127.0.0.1:<port>". Switching models, going back to Cloud, or
closing mesoSPIM stops the child. A server that fails to start is reported with the path of its
log. Use a GPU build of llama-cpp-python for anything above a few billion parameters; the 4B to 12B
instruction models are the realistic range on a microscope PC.

**Connect** applies the rows; a first message sent without pressing it applies them as typed.
Building a cloud endpoint does not contact the provider, so a wrong key shows up as an error on the
first message. The endpoint can be changed between turns and the transcript is kept. The presets
live in `mesoSPIM_AiAssistent_Config.py` as defaults only.

## Using it

Open the **AI Assistant** tab and type. Commands the agent runs stream live above each answer, so
the operator sees exactly which named calls were issued. `Interrupt` gates further dispatches and
halts the hardware.

## Limitations

These are known and deliberate; read them before using the tab on an instrument with a sample
loaded.

- **Six commands are gated by the operator, in code.** `load_sample`, `unload_sample`,
  `run_acquisition_list`, `run_selected_acquisition`, `preview_acquisition` and `time_lapse_start`
  do not execute until the operator presses **Run** in the bar that appears above the input; Cancel,
  Interrupt, or two minutes of silence count as Cancel, and the model is told the operator
  refused. This holds whatever the model was told or talked into.
- **The model call has no timeout.** `WAIT_CAP_S` bounds the microscope leg only. If the endpoint
  stalls — a burst over a tokens-per-minute quota is the usual cause — the turn blocks until the
  HTTP layer gives up, and `Interrupt` gates tool dispatch but cannot abort a request already in
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
