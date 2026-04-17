# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v0.1.0

### Added
- Project scaffolding: Tauri v2 + Vue 3 + TailwindCSS v4
- SQLite database layer for workflow persistence
- Python Sidecar with JSON-RPC over stdio
- Camoufox anti-detect browser integration
- Vue Flow workflow editor with drag-drop nodes
- Pseudocode DSL engine (parse ↔ compile bidirectional)
- Browser action recording via JS injection
- Workflow execution engine with conditions, loops, variables
- Auto-update support via Tauri updater plugin
- GitHub Actions CI/CD: Release (5 targets) / CI Check / Frontend Check / Clippy Lint
- Cross-compile: Windows x64/ARM64, Linux x64/ARM64/ARMv7
