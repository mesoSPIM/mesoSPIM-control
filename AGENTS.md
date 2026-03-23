# AGENTS.md

## Purpose
- This repository contains `mesoSPIM-control`, a Python/PyQt application for mesoSPIM light-sheet microscopes.
- The codebase mixes GUI code, acquisition logic, plugin infrastructure, docs, and hardware integrations.
- Many installations are customized per microscope; make narrow, reversible changes and avoid overwriting local hardware behavior.
- The worktree is often dirty and may include line-ending-only noise; inspect nearby changes before editing.

## Source Of Truth
- Main entry point: `mesoSPIM/mesoSPIM_Control.py`
- Main application modules: `mesoSPIM/src/`
- Hardware/config files: `mesoSPIM/config/`
- Plugins: `mesoSPIM/src/plugins/`
- Tests: `mesoSPIM/test/`
- Docs: `docs/source/`, published with Sphinx

## Agent Operating Rules
- Preserve user or lab-specific configuration. Do not rewrite example configs or hardware paths unless the task requires it.
- Prefer small, targeted edits over sweeping refactors.
- Match the surrounding file style instead of normalizing old code to a new standard.
- Be careful with files that may already have unrelated local edits.
- Treat built artifacts in `docs/build/` as generated unless the user explicitly asks to edit them.

## External Rule Files
- Existing `AGENTS.md`: none was present at repo root when this file was created.
- Cursor rules: no `.cursorrules` or `.cursor/rules/` files were found.
- Copilot rules: no `.github/copilot-instructions.md` file was found.

## Environment Notes
- Python target: `>=3.12` according to `pyproject.toml`.
- Core runtime dependencies are listed in `requirements-conda-mamba.txt`, `requirements-clean-python.txt`, and `pyproject.toml`.
- The app is typically run in a conda/mamba environment with PyQt5 and hardware libraries installed.
- Some commands below fail in a bare environment if optional dependencies like `PyQt5`, `pytest`, or hardware drivers are missing.

## Install And Run
- Create/install the main environment with `pip install -r requirements-conda-mamba.txt`.
- Alternative lightweight dependency list: `pip install -r requirements-clean-python.txt`.
- Launch demo mode from repo root with `python mesoSPIM/mesoSPIM_Control.py -D`.
- Launch demo mode from `mesoSPIM/` with `python mesoSPIM_Control.py -D`.
- Installed console script entry point: `mesospim-control`.

## Test Strategy Reality
- Automated coverage is limited because much of the software depends on physical hardware.
- Follow the repo's intended validation order: demo mode first, then real hardware if the change touches acquisition/device code.
- Unit tests exist in `mesoSPIM/test/`, but some are old, environment-sensitive, interactive, or hardware-dependent.
- Do not assume every historical test can run headlessly in CI.

## Test Commands
- Run all repository tests from the `mesoSPIM/` directory: `python -m pytest test/`.
- Run one test file: `python -m pytest test/test_tiling.py -q`.
- Run one pytest test by keyword: `python -m pytest test/test_tiling.py -k image_counts -q`.
- Run one unittest-style test directly: `python -m unittest test.test_tiling.TestTilingWizard.test_image_counts`.
- Run legacy module-style test command noted in the file: `python -m unittest test.test_tiling`.
- If running from repo root, many tests need `mesoSPIM/` on the import path because they import `src...` directly.
- Hardware-oriented tests like `test_serial.py` should only be run on the matching device setup.
- `test_writing_speed.py` is interactive and disk-heavy; do not run it in automation.

## Build And Verification Commands
- Syntax-check specific files: `python -m py_compile path/to/file.py`.
- Quick repo status: `git status --short`.
- Ignore CRLF-only noise while reviewing: `git diff --ignore-cr-at-eol --stat`.
- Review recent branch history: `git log --oneline --decorate -10`.
- Build docs on Linux/macOS: `make -C docs html`.
- Build docs on Windows: `docs\make.bat html`.
- Docs dependencies are not pinned separately; install `sphinx`, `furo`, `myst-parser`, and `sphinx-design` if missing.

## Lint And Formatting Reality
- No repo-level `ruff`, `black`, `isort`, `flake8`, or `mypy` configuration was found.
- There is no enforced autoformatter configuration in `pyproject.toml`.
- A `.ruff_cache/` directory exists, which suggests ad hoc local Ruff usage, but not a committed Ruff policy.
- Default to manual, minimal formatting changes.
- Do not mass-reformat files just because a local formatter would change them.

## Imports
- Follow the file's existing import layout unless you are touching the section anyway.
- In new or heavily edited files, prefer standard library imports first, third-party imports second, local imports last.
- Keep one import per line when practical; avoid comma-packed imports in new code.
- Prefer explicit imports over wildcard imports.
- Preserve local relative-import conventions inside `mesoSPIM/src/`.
- Be aware that some older modules rely on running from the `mesoSPIM/` directory and import `src...` directly.

## Formatting
- Use 4-space indentation.
- Keep whitespace changes minimal, especially in legacy modules.
- Match surrounding quote style; the repo uses both single and double quotes.
- Keep docstrings and UI strings concise.
- Avoid introducing non-ASCII unless the file already needs it.
- Avoid broad line wrapping churn unless you are already rewriting the block.

## Types
- Type hints are encouraged for new or significantly changed code, but they are not universal in the existing codebase.
- Add types where they improve clarity for APIs, plugin contracts, helpers, and non-trivial state structures.
- Do not force full typing retrofits across old PyQt or hardware modules.
- Prefer concrete container types when useful, e.g. `dict[str, Any]`, `list[str]`, `Path`.
- When extending plugin APIs, keep runtime behavior and documented types aligned.

## Naming Conventions
- Follow local naming conventions, even when they differ from strict PEP 8.
- Many classes use project-specific names like `mesoSPIM_MainWindow`; preserve that style in adjacent code.
- Use `snake_case` for new functions, methods, variables, and module-level helpers unless the file clearly uses a different convention.
- Use `CapWords` for new standalone classes unless a project-specific prefix is already established.
- Constants are generally uppercase when treated as constants.
- Plugin classes should expose stable classmethods like `name()`, `description()`, and `api_version()`.

## Error Handling And Logging
- Prefer raising specific exceptions (`ValueError`, `FileNotFoundError`, `ImportError`) when the caller can act on them.
- Use logging for operational context; many modules initialize `logger = logging.getLogger(__name__)`.
- Log actionable context with failures, especially for plugins, device I/O, and model loading.
- Avoid swallowing exceptions silently.
- If you must catch broad exceptions around optional hardware/plugin imports, log enough context to debug the failure.
- Preserve pass-through or fallback behavior where the application must stay usable without optional components.

## GUI And PyQt Guidance
- Keep signal/slot code explicit and readable.
- Avoid blocking the GUI thread with long-running work.
- When editing dialogs or windows, preserve existing widget wiring and state refresh behavior.
- For UI text, prefer practical operator-facing wording over framework jargon.
- Validate GUI-affecting changes in demo mode when possible.

## Plugin System Guidance
- Plugin discovery and contracts live under `mesoSPIM/src/plugins/`.
- Keep plugin API changes backward-aware; discovery is dynamic and may load external lab plugins.
- Do not break `ImageWriter` or `ImageProcessor` registration flows casually.
- When adding configurable processor parameters, keep `parameter_descriptions()` metadata and runtime `configure()` behavior consistent.
- Prefer clear failure messages for missing optional dependencies such as PyTorch-based processors.

## Hardware-Sensitive Areas
- Any code in `mesoSPIM/src/devices/`, waveform generation, stage control, or acquisition timing may affect real hardware.
- Preserve fallback behavior for demo mode.
- Do not remove safety warnings or initialization guards unless you understand the hardware consequence.
- Avoid changing default voltages, trigger ordering, or serial behavior without checking config interactions.
- If a change touches live acquisition or stopping behavior, call out the need for bench validation.

## Documentation Guidance
- Keep `README.md` and `docs/source/` aligned when both describe the same workflow.
- The Sphinx config in `docs/source/conf.py` includes mocks and platform shims so docs can build without hardware libraries.
- Prefer updating docs when behavior, plugin authoring, or setup steps change.
- Do not edit generated HTML in `docs/build/` unless explicitly asked.

## Practical Agent Workflow
- Before editing, inspect local diffs if the surrounding area may already be modified.
- After code changes, run the smallest reasonable verification command.
- For pure Python edits, `python -m py_compile ...` is a good low-risk baseline.
- For GUI changes, note whether validation was limited to static review, syntax check, demo mode, or real hardware.
- When test commands fail because dependencies are absent, report that clearly instead of guessing.

## Good Defaults For Future Agents
- Start from repo root unless a test explicitly expects `mesoSPIM/` as the working directory.
- For a single test, prefer `python -m pytest test/test_tiling.py -q` from `mesoSPIM/`.
- For a single unittest target, prefer `python -m unittest test.test_tiling.TestTilingWizard.test_image_counts` from `mesoSPIM/`.
- For docs-only changes, build docs if Sphinx is available; otherwise document the missing dependency.
- For hardware-facing changes, recommend manual demo-mode and on-instrument validation in the final note.

## Project-Specific Workflow Notes
- Use `PROJECT_CONTEXT.md` only for session-handoff notes: recent changes, current priorities, validation gaps, and open questions.
- Keep stable repo guidance in `AGENTS.md`; do not duplicate build commands, coding conventions, or evergreen architecture notes in `PROJECT_CONTEXT.md`.
- Read `PROJECT_CONTEXT.md` before starting work, and update it at the end of each work session so the next agent can get up to speed quickly.
- `PROJECT_CONTEXT.md` is ignored by git and will not be included in commits. Use it for local notes note only. If the file does not exist, create it.