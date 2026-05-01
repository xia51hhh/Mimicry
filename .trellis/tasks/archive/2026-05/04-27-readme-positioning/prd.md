# README and Project Positioning Cleanup

## Goal
Replace the scaffold README with accurate public-facing project documentation modeled after the Clippy README structure while keeping claims aligned with implemented behavior.

## Decisions
- Primary README is English: `README.md`.
- Chinese translation lives at `docs/README.zh-CN.md`.
- Product positioning should avoid over-emphasizing sensitive anti-detection/multi-account language.
- Preferred framing: local-first browser automation, isolated browser profiles, reproducible browser environments, visual workflows.
- Current features and roadmap must be separated explicitly.

## Scope

### In scope
- Rewrite root `README.md`.
- Add `docs/README.zh-CN.md`.
- Include project status: Alpha / MVP.
- Include badges for existing GitHub Actions workflows.
- Include current features based on existing code.
- Include Roadmap for not-yet-complete capabilities.
- Include Quick Start, Tech Stack, Architecture, Project Structure, Development Checks, Docs, Credits, License note.
- Mention known quality status honestly:
  - frontend lint currently needs cleanup;
  - Rust compiles but has no unit tests;
  - Python sidecar has stronger executor tests.

### Out of scope
- Adding a banner image.
- Adding a license file.
- Fixing lint/typecheck failures.
- Rewriting design docs beyond linking to roadmap items.

## Completion Criteria
- [x] Root `README.md` no longer contains Tauri template text.
- [x] `docs/README.zh-CN.md` exists and mirrors the English README.
- [x] README describes only implemented capabilities under Current Features.
- [x] Not-yet-implemented features are listed under Roadmap.
- [x] README does not claim a license exists when no `LICENSE` file is present.
- [x] Links point to existing local docs or existing GitHub workflow files.
