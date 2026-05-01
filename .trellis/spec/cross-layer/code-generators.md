# Code Generators Must Pre-Format Their Output

## Scope

Any script under `scripts/` that **writes** source files into the repo (e.g. `sync-action-map.py` regenerating `src/types/action-map.ts` and `sidecar/engine/action_map.py`).

## Rule

A code generator's output MUST pass the project's formatter for that file's language **without further re-formatting**. Specifically:

- TypeScript / JavaScript / Vue / CSS / JSON output → must satisfy `prettier --check` (this repo: single quotes, trailing commas, 2-space indent, `; on multi-line function args)
- Python output → must satisfy `ruff format --check` (when ruff is added; until then, match surrounding repo style: double quotes, 4-space indent)
- Rust output → must satisfy `cargo fmt -- --check`

## Why

A generator that emits "almost correct" output sets a trap:

1. The generator passes its own validation step (`--fix` succeeds, files written).
2. The user thinks the contract is satisfied.
3. The next CI run trips on `prettier --check` / `cargo fmt --check`, blocking the PR.
4. The user runs `pnpm format` / `cargo fmt`, files now look "wrong" to the generator's parser.
5. CI now trips on `sync-*.py` complaining about drift it just caused.

This was hit on 2026-05-01 with `scripts/sync-action-map.py`: it emitted double-quoted TS, Prettier wanted single-quoted, the parser regex only accepted double-quoted, so `--fix` and `prettier --write` fought each other. Both the generator and the parser had to be fixed in one commit.

## How to apply

When writing a new generator, or modifying one:

1. Read the project formatter config first (`prettier --check --debug-check <file>`, `.prettierrc`, `rustfmt.toml`).
2. Make the **emitter** match the formatter's expected output exactly.
3. Make the **parser** (if the script also reads back the file) accept both formatter-normalized output AND any minor variant a human might commit (e.g. accept both quote styles for TS).
4. Add the generator's check step to CI **after** the formatter check, not before. If they ever produce conflicting output, the CI failure will be visible at the formatter step first, which is the cheaper signal.

## Verification recipe

For TS generators in this repo:

```bash
python3 scripts/<generator>.py --fix
pnpm format:check          # MUST pass with no warnings
python3 scripts/<generator>.py    # MUST report "in sync"
```

If either fails immediately after `--fix`, the generator is buggy.

## Related contracts

- `shared/action-map.json` is source of truth for action names — see `.trellis/spec/cross-layer/block-schema.md`.
- `scripts/sync-action-map.py` is the generator covered by this rule.
