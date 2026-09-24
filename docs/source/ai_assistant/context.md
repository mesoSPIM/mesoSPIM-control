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
- **A session store with two recall tools.** Every turn is kept in full for the session (the
  operator's words, the readout, the tool calls with results, the reply), so compaction loses
  nothing: `recall_turn` returns an earlier turn in full or the turns in which a readout key
  changed, an exact lookup since readouts are structured; `search_history` finds earlier turns by
  words in messages, replies and results, which needs no model and works offline. Two evaluation
  cases run with a two-turn memory, so only the store can answer them. Clear context empties the store.
- **Large results shortened at the source.** The acquisition list keeps every row with the
  operator-facing keys only (up to 60 rows); any other result over 3,000 characters keeps the
  top-level keys that fit and names the ones left out, so the model can ask for them.
- **The single-acquisition start refers to the row schema** like the checks do.
- **The prefix is byte-identical across requests**: instructions and tool schemas carry nothing
  time-dependent, and a test compares two builds. A profile switch rebuilds the agent, which is
  the one legitimate change of the prefix.

- **One round trip where one does the job.** On a local model every tool call costs seconds.
  The traces showed one systematic waste, a snap right before a look, which snaps by itself; the
  snap tool now says so in its description, the manual says so, and the scorer fails any case
  that does it within a turn. Confirmation reads after an action did not occur on flash-lite.

## Still open, in order of payoff

### 1. Embeddings for the history search, when words prove too literal

`search_history` matches words. It answers "which batch did I say" but not "did we do anything
about the illumination earlier" when the earlier turn said "laser too strong". A small local
embedding model over the same store, or the provider's embeddings, would close that; it is the
one place vectorization earns its place, an unstructured, growing corpus and questions of the
form "did we ever". The manual stays out of it: its rules must be present before the model
decides anything, and an ambiguous request or a planted note is exactly the case where the
relevant rule does not look relevant to a retriever.

### 2. Tools on demand

The 37 schemas are the largest fixed part, and a third of them (acquisition list, runs,
previews, time lapse) are untouched by most turns. pydantic-ai has this built in: tools marked
`defer_loading=True` stay hidden until the model asks its `ToolSearch` capability for them
(provider-native on Anthropic and OpenAI, keyword matching elsewhere). A core set of about
twenty tools always present and the acquisition group deferred would cut roughly a thousand
tokens per request, at the cost of one extra round trip the first time a run is requested and
a new failure mode, a model that does not find a tool, which the evaluation would have to cover
before this ships.

### 3. Slimmer schemas, and a Minimal tool set

In the Full set `set_state` alone is 3K characters. Since a rejected call comes back as data
with the instrument's own vocabulary, a schema could list names and types and leave ranges to
the error path. A Minimal set of about fifteen commands (moves, optics, snap, look, live, stop,
the reads) would halve the schema cost again for a small local model.

### 4. The manual, last

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
