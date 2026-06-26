# Module Split Task Context

Worktree: assign this task to a dedicated feature worktree.
Suggested branch: `dev-module-split`
Baseline: start from latest `dev-env`.

Purpose:
- Separate the packaging/API boundary question from the test-environment work.
- Decide which modules remain installable runtime package code under `src/raser`.
- Move or plan movement of one-off studies, examples, scripts, and tests out of the public package.
- Design a real pytest layout that verifies RASER behavior instead of placeholder assertions.

Start here:
- Run `git status --short --branch` and confirm the worktree is clean.
- Read `pyproject.toml`, `README.md`, `src/raser/__main__.py`, `env/setup.sh`, and the current `src/raser` package tree before editing.
- Keep all work inside the assigned worktree.
- Do not migrate old local WIP from another machine. Treat it only as historical clues.
- Do not change supported Python versions, dependency pins, CI triggers, or packaging metadata unless the task explicitly requires it.

Scope:
- Produce a concrete module classification:
  - public runtime package modules that remain under `src/raser`;
  - CLI/workflow modules that remain importable only because the CLI routes to them;
  - examples, studies, plotting scripts, hardware-control scripts, and batch utilities that should live outside `src`;
  - tests and test fixtures that should live under top-level `tests/`.
- Propose or implement the smallest safe file movement needed to make that boundary clearer.
- Replace placeholder tests with behavior tests where practical.

Initial assertions to verify:
- `src/raser` should contain code needed after installation for `import raser` or `python -m src.raser ...`.
- Top-level `tests/` should own pytest tests; `src/raser/tests` should not be the long-term test location.
- `src/raser/tests/test_draw.py` and `src/raser/tests/test_field.py` currently test only Python `sum`, not RASER behavior.
- `src/raser/tests/__pycache__` should not be a tracked package artifact.
- `misc/**` is already package-external and is a better home for ad hoc control, plotting, and formula scripts than `src/raser`.

Likely keep in `src/raser`:
- `__main__.py` as the CLI entrypoint.
- `device`, `field`, `current`, `interaction`, `signal`, `tct`, `afe`, `resolution`, and `util` as runtime package modules, subject to local code review.
- Domain workflows such as `bmos`, `lumi`, `telescope`, `dfe`, `mcu`, and `cce` only if README/CLI behavior treats them as supported workflows. Keep reusable runtime code; move one-off scripts out.

Likely move out of `src/raser` or split:
- placeholder tests under `src/raser/tests`;
- `src/raser/mcu/regincr_test.py`;
- paper-specific plotting, sample, precision, and scan-draw scripts if they are not CLI-supported runtime modules;
- shell scripts and generated/runtime artifacts inside package directories;
- one-off batch reprocessing scripts if they are not part of the supported import or CLI surface.

Suggested destination layout:
- `tests/` for pytest tests and fixtures.
- `examples/` for small user-facing examples.
- `studies/` for detector, paper, and analysis reproductions.
- `scripts/` for maintainer or batch utilities.

Pytest design:
- Add pytest as a development/test dependency only through the repository's chosen dependency route.
- Default tests should avoid requiring ROOT, devsim, g4ppyy, Geant4, ngspice, hardware, or external services.
- Use explicit markers for heavy or optional dependencies:
  - `root`
  - `devsim`
  - `geant4`
  - `ngspice`
  - `hardware`
- Default CI/local smoke command should run pure Python behavior tests and skip heavy markers.
- Heavy integration tests should be opt-in and should fail visibly when prerequisites are missing.

High-value first tests:
- CLI parser routes each subcommand to the expected module without running the simulation.
- detector configuration loading validates required fields and reports missing files clearly.
- weighting-potential missing or exceptional values are handled visibly and deterministically.
- current/bin accumulation behavior is equivalent for representative numeric inputs.
- `--no-plots`, if implemented elsewhere, changes only plot generation and not signal/tree outputs.
- resolution code reports empty or undersized input trees clearly instead of producing misleading numbers.

Verification expectations:
- For any moved module, prove the supported CLI/import path still works.
- For any moved script, update references or document the new location.
- Run focused pytest tests added by this task.
- Before marking ready, run repo validation commands if available:
  - `make format`
  - `make lint`
  - `make typecheck`
  - `make tests`
- If those Makefile targets do not exist or cannot run, report the exact limitation.

Out of scope:
- Do not perform performance work from `dev-boost`.
- Do not run long detector simulations or 500-valid-event production jobs.
- Do not redesign the whole package API in one pass.
- Do not add broad compatibility shims unless a specific supported import path would otherwise break.
