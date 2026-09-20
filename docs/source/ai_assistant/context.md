# Context budget and optimizations

What a turn costs the model, what has been done about it, and what could still be done, in the
order of payoff. Every number here was measured with Gemini's token counter on the Regular tool
set; the evaluation in `mesoSPIM/test/ai_assistant/evals/` is the judge of every change, with
the scoreboard as the record.

## What a request carries today

| Part | Tokens | Notes |
|---|---|---|
| Manual, and the commands by kind | ~1,700 | the rules; every one of them came from a failure the evaluation found |
| Tool schemas, 37 tools | ~3,300 | the price of function calling; the acquisition row is spelled out once |
| State block of the newest message | ~500 | the readout the model acts on |
| Fixed cost per request | ~5,500 | was 7,400 before the slimming |

Then the memory: up to twenty operator turns. Before compaction each carried its 500-token
readout and every tool result in full, so a long session added up to ten thousand tokens of
stale readouts, more than the system prompt. Now the newest three turns stay whole and older
ones keep a one-line readout (state, position, optics) and shortened tool results, applied by
pydantic-ai's `ProcessHistory` before every model request. On the free tiers the per-request
size is what trips the per-minute token cap; on a local model with an 8K or 32K window it is
what leaves room for the conversation.

## Done

- **Commands by kind** in the prompt instead of one line per command; the tool descriptions
  carry what each does.
- **Acquisition rows by reference** in the disk-space and motion-limit checks; the row schema
  is spelled out once, in `set_acquisition_list`.
- **Plumbing reads Full-only** (ping, hello, the raw state map, the stuck-operation reset).
- **History compaction** as above, with "put it back to what it was" still answerable from
  the compact readout.
- **The readout before the operator's words**, so the fixed prefix is followed by the readout
  and the request comes last, which is also what stopped a small model copying the block.
- **A size guard** in the tests, so the prompt cannot creep back.

## Still open, in order of payoff

### 1. Past states as a store with a recall tool, and vector search where it fits

Compaction keeps only a one-line readout of older turns, but past states matter: "what was
the focus before I moved it", "when did the intensity change", "what did we do with the 561
laser earlier". The full readouts should not travel with every request; they should be stored
and asked for.

- **Store**: every turn already lands in the trace file (`assistant-<date>.jsonl`): the
  prompt, the readout, each tool call and result, the reply. Keeping the same records in memory
  for the session, keyed by turn number and time, costs nothing extra.
- **Exact recall**: a `recall` tool that returns the full readout of turn N, or of the turn
  nearest a given time, or the turns in which a named value changed. Readouts are structured, so
  this is a lookup, not a search, and it is exact.
- **Semantic recall**: a `search_history` tool over the free text of the session (operator
  messages, replies, tool results). Start with keyword matching, which needs no model and works
  offline for a local setup; add embeddings (a small local embedding model, or the provider's)
  when keyword matching proves too literal. This is the one place vectorization earns its
  place: unstructured text, a growing corpus, and a question of the form "did we ever ...".
- **What not to vectorize**: the manual. Its rules must be present before the model decides
  anything, and an ambiguous request or a planted note is exactly the case where the relevant
  rule does not look relevant to a retriever. Provider-side prefix caching is the right tool
  for that part.

### 2. Tools on demand

The 37 schemas are the largest fixed part, and a third of them (acquisition list, runs,
previews, time lapse) are untouched by most turns. pydantic-ai has this built in: tools marked
`defer_loading=True` stay hidden until the model asks its `ToolSearch` capability for them
(provider-native on Anthropic and OpenAI, keyword matching elsewhere). A core set of about
twenty tools always present and the acquisition group deferred would cut roughly a thousand
tokens per request, at the cost of one extra round trip the first time a run is requested and
a new failure mode, a model that does not find a tool, which the evaluation would have to cover
before this ships.

### 3. Cap large tool results at the source

`get_config`, `get_acquisition_list` and `get_frame` can each return more than the whole
system prompt. Compact forms by default, with the detail on request, keep a single read from
flooding a turn. Compaction shortens them in older turns only; the turn they arrive in pays
in full.

### 4. Keep the fixed prefix byte-identical

Gemini, Anthropic, llama.cpp, Ollama and vLLM all reuse a cached prefix that has not changed.
The prefix is the instructions and the tool schemas; the readout and the request follow. Two
things would break the cache and must stay out of the prefix: anything time-dependent, and the
tool list changing between turns (a profile switch rebuilds the agent, which is fine; a per-turn
change would not be).

### 5. Slimmer schemas, and a Minimal tool set

`acquire_start` still spells out the full row; by reference it saves about 300 tokens. In the
Full set `set_state` alone is 3K characters. Since a rejected call comes back as data with the
instrument's own vocabulary, a schema could list names and types and leave ranges to the error
path. A Minimal set of about fifteen commands (moves, optics, snap, look, live, stop, the
reads) would halve the schema cost again for a small local model.

### 6. The manual, last

It is 1,700 tokens and holds the safety rules. Every sentence in it was added because a
model without it did something wrong, so cutting it is the lowest payoff and the highest
risk. Rewording for brevity is fine; removing rules is not.

## How to measure a change

```
python -m mesoSPIM.test.ai_assistant.evals.run --provider Gemini --model <model> --repeat 2 \
    --out "mesoSPIM/test/ai_assistant/evals/runs/{date}-{model}.jsonl"
python -m mesoSPIM.test.ai_assistant.evals.scoreboard mesoSPIM/test/ai_assistant/evals/runs/*.jsonl
```

A change to the context is kept only if the scoreboard holds on every model it is meant for,
including the smallest one; the memory, vision and looking cases are the ones a context change
can break.
