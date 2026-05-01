# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Mimicry — a local-first desktop browser automation app. Three-layer stack:

```
Vue 3 WebView ──invoke()/emit()──► Rust Core ──stdio JSON-RPC 2.0──► Python Sidecar ──► Camoufox
   src/                              src-tauri/src/                    sidecar/
```

- **Frontend** (`src/`): Vue 3 + TS + Pinia + Vue Flow canvas + Monaco editor + Tailwind v4 + vue-i18n (en / zh-CN)
- **Rust core** (`src-tauri/src/`): Tauri v2 commands, SQLite via `rusqlite`, sidecar lifecycle + JSON-RPC client
- **Python sidecar** (`sidecar/`): Camoufox/Playwright controller, workflow executor, recorder, RPC server

## Common commands

```bash
# Full-stack dev (starts Vite on :1420 + Rust shell)
cargo tauri dev

# Frontend only
pnpm dev              # Vite dev server
pnpm build            # vue-tsc --noEmit && vite build
pnpm typecheck        # vue-tsc --noEmit
pnpm lint             # ESLint over src/
pnpm format           # Prettier over src/
pnpm test             # vitest run
pnpm test:watch

# Rust (run from src-tauri/)
cargo check
cargo test --all-targets --all-features
cargo clippy --all-targets --all-features -- -D warnings
cargo tauri build     # release bundle → src-tauri/target/release/bundle/

# Python sidecar (from sidecar/, with its venv active)
pip install -r requirements-dev.txt
python -m pytest                           # full suite
python -m pytest tests/test_executor.py    # single file
python -m pytest tests/test_executor.py::test_name -v
```

The sidecar venv is created on first launch under the OS app-data dir (`com.mimicry.app/venv/`), not inside the repo. `src-tauri/src/lib.rs::resolve_sidecar_dir` finds the `sidecar/` source directory in dev.

## Sidecar has three entry modes — they share the same browser/action layer

```
1. Tauri Sidecar  : Tauri Shell  ── stdio JSON-RPC ──► sidecar/main.py
2. CLI + Daemon   : sidecar/cli.py ── UDS socket  ──► sidecar/daemon.py
3. MCP Server     : LLM client  ── stdio MCP    ──► sidecar/mcp_server.py
```

All three dispatch through the same `sidecar/browser/actions.py` adapter and `sidecar/rpc/methods.py` registry. When changing browser behavior, the change applies to all three modes — no per-mode duplication. See `sidecar/SKILL.md` for the LLM-facing CLI guide and `docs/dev-cli.md` for command reference.

## Critical conventions

- **Package manager**: pnpm `10.12.1`, locked via `packageManager` in `package.json`. Do not switch to npm/yarn.
- **Version triple lock**: `package.json`, `src-tauri/tauri.conf.json`, `src-tauri/Cargo.toml` versions must match (CI enforces). Releases are triggered by `vX.Y.Z` git tags and require a matching `## vX.Y.Z` section in `CHANGELOG.md`.
- **Vue style**: `<script setup lang="ts">` Composition API only. No Options API.
- **Pinia stores**: `defineStore("name", () => { ... })` setup syntax. Stores live in `src/stores/`.
- **TypeScript**: strict mode (`strict`, `noUnusedLocals`, `noUnusedParameters`). `_`-prefixed args are exempt from the unused-vars rule. `any` is a warning, not an error.
- **i18n**: every user-visible string goes through `t(...)`. Locales in `src/locales/{en,zh-CN}.json`.
- **Action-map sync (cross-layer contract)**: `shared/action-map.json` is the source of truth for frontend action names → backend method names. After editing it, run `python scripts/sync-action-map.py` to validate that `sidecar/engine/action_map.py` and `src/types/action-map.ts` are in sync. CI runs this script.
- **ADR-001 — JSON direct execution**: workflows are JSON node graphs (`kind + action + data + settings`), not a DSL. `sidecar/dsl/` is deprecated and retained for reference only — do not extend it. See `docs/design/decisions.md`.
- **DB**: SQLite at `<app-data>/com.mimicry.app/mimicry.db`, schema initialized in `src-tauri/src/db/schema.rs`. Tables: `workflows`, `settings`, `recent_files`, `profiles`.

## Architecture pointers

When work spans layers, read these first:

- `docs/architecture.md` — module map, IPC layout, three sidecar modes
- `docs/design/decisions.md` — six ADRs covering execution model, selectors, loops, debugging, error handling, packages
- `docs/design/block-system.md` — canonical block JSON schema (the cross-layer contract)
- `.trellis/spec/cross-layer/block-schema.md` — recorder output, action naming, session routing
- `.trellis/spec/frontend/` — frontend conventions broken out by topic (state, components, types, hooks)
- `docs/llm-interactive-guide.md` — patterns for driving the browser via CLI/MCP

## Trellis workflow

This repo uses the Trellis task system. The active task is tracked in `.trellis/.current-task` and surfaced via the SessionStart hook. Tasks live under `.trellis/tasks/{MM-DD-name}/` with `prd.md`, `implement.jsonl`, `check.jsonl`. The standard flow per task is `trellis-implement → trellis-check → trellis-update-spec → finish`. See `.trellis/workflow.md` and `AGENTS.md` for the full protocol — including when to dispatch sub-agents instead of editing in the main session.
