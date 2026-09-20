# Testing a local model on a Mac

The steps to run the assistant against a model file on an Apple-silicon Mac, with the same
evaluation that judged the cloud models. Nothing here touches a microscope: demo mode stands in
for the instrument, exactly as in the offline tests. Times are for an M-series Mac with 16 GB or
more; a 12B model needs the 16 GB, a 4B model runs on 8 GB.

## 1. Get the branch and a Python 3.12 environment

```
git clone https://github.com/thomdehoog/mesoSPIM-control.git
cd mesoSPIM-control
git checkout remote-control-py312
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-clean-python.txt
pip install -e ".[ai-assistant]"
```

## 2. Install llama.cpp with the Metal build

The plain wheel runs on the CPU only. The Metal build uses the GPU and the unified memory:

```
CMAKE_ARGS="-DGGML_METAL=on" pip install --no-cache-dir "llama-cpp-python[server]>=0.3"
```

This compiles for a few minutes. If it fails, `xcode-select --install` first.

## 3. Put a model file in the models folder

```
mkdir -p ~/mesoSPIM/models
```

Download a quantised GGUF from Hugging Face into it. Two that fit the purpose, with the
projector file that lets the model see the camera frame:

| Model | File | For vision, also |
|---|---|---|
| Gemma 3 12B, Q4_K_M, ~7 GB | `gemma-3-12b-it-Q4_K_M.gguf` | `mmproj-gemma-3-12b-it-f16.gguf` |
| Gemma 3 4B, Q4_K_M, ~2.5 GB | `gemma-3-4b-it-Q4_K_M.gguf` | `mmproj-gemma-3-4b-it-f16.gguf` |

The projector is matched to the model by the family in its name (the first two dash-separated
tokens, `gemma-3`), so keep the names as downloaded. Any other GGUF with tool calling works the
same way; Qwen 3 8B is a good third choice.

## 4. Try the tab in demo mode

```
python mesoSPIM/mesoSPIM_Control.py -D
```

Open the **AI Assistant** tab, set Type to **Local AI**, pick the file, Connect. The button reads
"Starting…" while the model loads, then "Connected". Ask "Where is the stage?", then "Take a snap
and tell me what you see". The transcript shows each tool call under the reply; the frame the
vision model was shown appears in it too. Every turn is written to
`~/mesoSPIM/assistant_traces/assistant-<date>.jsonl`.

## 5. Run the evaluation against the model

Close the tab's connection first (Clear all is not needed; the evaluation starts its own server).
Then, from the repository root:

```
python -m mesoSPIM.test.ai_assistant.evals.run \
    --local ~/mesoSPIM/models/gemma-3-12b-it-Q4_K_M.gguf \
    --out "mesoSPIM/test/ai_assistant/evals/runs/{date}-{model}.jsonl"
```

It serves the file as the tab does, waits until the model answers, runs the 110 cases and prints
one line per case, then the failures with what the model did instead. On a 12B model on an M2 or
M3 expect one to three seconds a turn after the first, and about ten minutes for the whole set;
a 4B model is faster. Add `--only vision-counts-spots,look` to try a couple of cases first, or
`--repeat 3` to see which cases are a coin flip.

To evaluate a server that is already running instead, such as Ollama or llama.cpp's own
`llama-server`, point the OpenAI-style preset at it:

```
python -m mesoSPIM.test.ai_assistant.evals.run --provider OpenAI-style \
    --base-url http://localhost:11434/v1 --model gemma3:12b --vision
```

Ollama needs one thing first. It loads a GGUF model with a 4,096-token context window unless told
otherwise, and one request here is about 6,000 tokens (instructions, tool schemas, the readout), so
every case fails in a tenth of a second with "request (6144 tokens) exceeds the available context
size". Give the server 16,384 or more, either for all models (`OLLAMA_CONTEXT_LENGTH=16384` in the
server's environment) or with a copy of one:

```
printf 'FROM gemma3:12b\nPARAMETER num_ctx 16384\n' > Modelfile
ollama create gemma3-12b-16k -f Modelfile
```

`ollama ps` shows the window a loaded model got. The MLX builds (`gemma4:e4b-mlx`) show 4096 there
too but are not held to it: they read a 12,000-token prompt whole. The tab reports this failure
with the same advice.

## 6. Read the result

```
python -m mesoSPIM.test.ai_assistant.evals.scoreboard mesoSPIM/test/ai_assistant/evals/runs/*.jsonl
```

The scoreboard puts the local model next to the cloud runs, per category, with the cases that
pass only sometimes or never. Three things to look at first:

- **Did it call tools at all?** If most cases fail with "expected a call to ..." and the replies
  are prose describing what it would do, the server did not present the tools to the model.
  llama-cpp-python picks a chat format from the file; a model that needs an explicit one can be
  started by hand with `python -m llama_cpp.server --model <file> --chat_format chatml-function-calling`
  and evaluated through `--base-url`. If that works and the default does not, that is the
  finding: the tab's Local AI mode should start the server with that format, or use
  `llama-server --jinja` from llama.cpp itself.
- **Vision.** The vision cases need the projector file beside the model; without it the
  `look` results say "this model cannot see images" and those cases fail honestly.
- **The quoted state block and the wasted snap.** Both are scored on every case; a local model
  that does either shows it in the failure text, and the tab already strips the block.

Send the run file, or the trace file from step 4, and the scoring and the reading of what the
model did can happen anywhere.
