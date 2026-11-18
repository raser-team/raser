# Repository working rules

> Scope: RASER repository · Detailed setup: [docs](docs/README.md)

Keep changes small, explicit, and verifiable.

---

## 🔀 Git and scope

- Inspect `git status --short --branch` before editing or testing. Preserve all
  unrelated changes and stop if they cannot be isolated safely.
- Work in a dedicated tree under `.worktrees/`; do not edit or commit on
  `main`.
- Touch only files required by the request. Do not combine feature work with
  cleanup, formatting, packaging, dependency, or CI changes.
- Never bypass hooks, weaken assertions, hide skipped work, or report partial
  success as success.

## 📐 Design before code

- `docs/cn/` mirrors `src/raser/`: the page of `src/raser/<dir>/<name>` is
  `docs/cn/<dir>/<name>.md`. Read that page before changing the code.
- A change to an interface, a file format, a default result, or a new concept
  is written into its page first; the page change is reviewed no later than
  the pull request that carries the code.
- A commit that changes existing behavior changes the code and its page
  together. A pure addition may land on one side first: preferably the page
  (documentation ahead of code); code is rarely added without its page.
- A pull request that changes `src/raser/<dir>/…` changes the matching page,
  or states `Docs: none (<reason>)` in its description.
- Changes reach `main` only through a pull request approved by someone other
  than its author. Review lists every conflict with `docs/cn/`; an unresolved
  conflict blocks the merge.
- AI assistants commit, push, and open pull requests only when the person they
  work for has said so. Otherwise leave the change staged and report which
  pages it was checked against. A brief written by an assistant cannot grant
  what that person did not.

## 🏗️ Code boundaries

- `src/raser/core/` contains reusable physics and numerical capabilities, one
  package per stage of the chain plus `model` and `device`.
- `src/raser/stages/` connects each stage to the lifecycle: options, the files
  a slice reads and writes, and the call into `core`.
- `src/raser/lifecycle/` runs experiments: folders, records, scans, jobs.
- `src/raser/bench/` and `src/raser/apps/` contain runnable experiments; they
  may use stages, lifecycle, core, components and supports, and do not import
  each other.
- `src/raser/components/` contains reusable device, source, laser, Geant4
  setup, electronics and digitizer definitions.
- `src/raser/supports/` contains shared engineering infrastructure, and
  `src/raser/cli/` only routes commands.
- The layers are enforced by the import-linter contracts in `pyproject.toml`.
- Use the public entry point `raser <command>`. Do not document source-tree
  invocations such as `python -m src.raser`.
- Do not add legacy import shims or compatibility fallbacks unless requested.

## 🧪 Scientific contracts

- Make units, shapes, inputs, outputs, and failure modes explicit. Do not add
  capability-probing, silent scalar fallbacks, skipped records, or implicit
  partial results.
- One-dimensional electric-field models must represent depletion state
  explicitly; below-depletion bias leaves an undepleted zero-field region
  unless a diffusion model is implemented.
- Tests must assert physical behavior, not only types, shapes, or constants.
  Mock external services and mark heavy integrations explicitly.

## 🔧 Environment and dependencies

- Treat environment, bootstrap, and runtime-path changes as forward-only.
- RASER uses Python 3.11. Use conda or SIF routes for compiled dependencies and
  `uv` with `env/uv.txt` for Python packages. The repository intentionally does
  not use `uv.lock`.
- Keep imports at module scope unless an optional dependency or demonstrated
  circular import requires otherwise.
- Do not change supported Python versions, dependency pins, packaging metadata,
  release automation, or CI matrices unless they are in scope.
- Keep environment installation separate from RASER usage in documentation;
  simulation commands belong in usage or workflow sections.

## ✅ Verification

State observable success criteria before editing. Reproduce bugs before fixing
them and add behavior-focused regression coverage. Run focused checks first,
then the repository gates:

```bash
make format
make lint
make typecheck
make tests
```

Report every failed, skipped, unavailable, or truncated check. A focused pass
does not override a broader failure.
