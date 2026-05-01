# Cross-Layer Specs

Contracts and conventions that span multiple layers (Frontend ↔ Rust ↔ Python).

## Files

- [block-schema.md](block-schema.md) — Canonical workflow node schema, action naming, session routing, recorder output format
- [code-generators.md](code-generators.md) — Rule for any `scripts/` generator that writes source files: output must pre-satisfy the language formatter (Prettier / cargo fmt / ruff format)
