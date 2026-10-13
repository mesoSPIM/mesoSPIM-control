# Skills

A skill is a short procedure the AI Assistant follows when a request calls for it: centring the
sample, finding focus, preparing and running an acquisition. The general instructions stay short
and work on any microscope; a skill is where a lab writes down how *its* instrument is best
handled, with its own step sizes, thresholds and order of steps.

## How the assistant uses them

1. At **Connect**, the tab reads every skill file in the microscope's `skills` folder and writes
   in the transcript which it found, and why a file was left out.
2. The model's instructions list each skill by its name and its one-line description only.
3. When a request matches a description, the model calls `load_skill` with that name before it
   changes anything; a first look is allowed. Only then does it receive the steps, so ten skills cost ten lines, not ten pages.
4. The model follows the steps with the usual tools (`look`, `move_relative`, `set_intensity`,
   ...). A skill gives no new powers: everything still goes through the same commands, checks and
   limits.

When no description matches, the model works without a skill.

## Where they live

One file per skill, all in one folder next to the microscope's config file:

```
mesoSPIM/config/
├── my_microscope_config.py
└── skills/
    ├── centring.md
    ├── focusing.md
    └── exposure.md
```

Add a skill by adding a file, remove one by deleting it. The folder belongs to the lab and is
versioned with its config; mesoSPIM ships no skills.

## Writing one

A skill is a Markdown file with a head between two `---` lines and the steps below it:

```markdown
---
name: centring
description: Bring the sample to the middle of the camera image.
tools: look, calibrate, move_relative
---
When: the operator wants the sample centred, or says it is off to one side or not in the middle.

1. look, asking "where is the sample in the image?". If no sample is visible, say so and stop.
2. If the frame's centre_move_um is marked nominal and calibrate is offered, run calibrate once.
3. move_relative by the frame's centre_move_um, x and y together.
4. look again. Done when offset_px is under about a tenth of the frame's width in both directions.
   Otherwise repeat steps 3 and 4, at most three moves in all.

Report where the sample started, the moves made and where it ended. If it did not get there,
say what offset remained.
```

- **name**: short, lower case, unique in the folder. It is what `load_skill` is called with.
- **description**: one line. This is the only part the model sees until it loads the skill, so
  it decides when the skill is used. Say what the skill achieves, not how.
- **tools**: the tools the steps use, comma-separated. The tab warns at Connect when one does not
  exist, for example after a rename.
- **The body**: when it applies, the steps in order with the tool for each, what to check after a
  step, when it is done, and what to report.

Good skills:

- **Cover a short request with a long procedure.** "Focus" needs a skill; "look, and run the
  list only if it is sharp" does not, because the request already says every step.
- **Do one job.** Keep each under half a page; the hard limit is 6,000 characters. A loaded skill
  stays in the conversation and is paid for on every later request.
- **Use the real tool names and fields** (`centre_move_um`, `focus_measure`, `saturated_fraction`).
  The model already has each tool's full description; the skill says how to combine them.
- **Say when to stop.** Without a stop rule a model loops, or stops too early. A bound on the
  number of rounds is the simplest.
- **Say what to report**, so the operator can see what was done.
- **Hold the lab's numbers.** Step sizes, thresholds and safe intensities belong here, not in the
  general instructions.

## Testing one

Try each skill in demo mode first, then on the microscope with an operator watching. Check both
sides: two or three requests that should use it, worded the way people actually talk ("I can only
see half the specimen"), and a similar request that should not ("move x by 100 µm" must not start
centring). The fork's evaluation has a benchmark that does this with five test skills
(`mesoSPIM/test/ai_assistant/evals/skills/`): run it with
`python -m mesoSPIM.test.ai_assistant.evals.run --cases mesoSPIM/test/ai_assistant/evals/cases_skills.json --skills <folder>`.
