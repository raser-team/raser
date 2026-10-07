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

## 🏗️ Code boundaries

- `src/raser/core/` contains reusable physics and numerical capabilities.
- `src/raser/components/` contains reusable detector, source, electronics, and
  ACTS definitions.
- `src/raser/apps/` contains runnable workflows; apps may use Core, Components,
  and Supports, but Core and Components must not import apps.
- `src/raser/supports/` contains shared engineering infrastructure, and
  `src/raser/cli/` only routes commands.
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

## 协作开发规范

本仓库已选择正式多人协作开发流程。开始功能设计、实现或验证任务前，完整读取并遵守 `~/.codex/policies/collaborative-development.md`。
本文件和 `docs/AGENTS.md` 的项目约定优先；Git 隔离、代码边界、科学契约、环境和验证要求沿用上文，共享规范补充未约定的文档、状态、日志与 worktree 生命周期要求。
