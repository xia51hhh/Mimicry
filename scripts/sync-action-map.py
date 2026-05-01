#!/usr/bin/env python3
"""Validate that Python and TypeScript action maps stay in sync with shared/action-map.json."""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "shared" / "action-map.json"
PY_PATH = ROOT / "sidecar" / "engine" / "action_map.py"
TS_PATH = ROOT / "src" / "types" / "action-map.ts"


def load_json() -> dict[str, str]:
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def parse_python() -> dict[str, str]:
    text = PY_PATH.read_text(encoding="utf-8")
    pairs: dict[str, str] = {}
    for m in re.finditer(r'"(\w+)"\s*:\s*"(\w+)"', text):
        # Only capture entries inside FRONTEND_TO_BACKEND block
        pairs[m.group(1)] = m.group(2)
    # Filter: keys should be PascalCase (start with uppercase)
    return {k: v for k, v in pairs.items() if k[0].isupper()}


def parse_typescript() -> dict[str, str]:
    text = TS_PATH.read_text(encoding="utf-8")
    # Extract the FRONTEND_TO_BACKEND object block
    block_match = re.search(
        r"FRONTEND_TO_BACKEND[^{]*\{([^}]+)\}", text, re.DOTALL
    )
    if not block_match:
        print("ERROR: Cannot find FRONTEND_TO_BACKEND in TypeScript file")
        sys.exit(2)
    block = block_match.group(1)
    pairs: dict[str, str] = {}
    # Accept both single and double quotes (Prettier uses single in this repo).
    for m in re.finditer(r"""(\w+)\s*:\s*['"](\w+)['"]""", block):
        pairs[m.group(1)] = m.group(2)
    return pairs


def compare(source: dict[str, str], target: dict[str, str], source_name: str, target_name: str) -> list[str]:
    errors: list[str] = []
    for key in sorted(set(source) - set(target)):
        errors.append(f"  Key '{key}' in {source_name} but missing from {target_name}")
    for key in sorted(set(source) & set(target)):
        if source[key] != target[key]:
            errors.append(
                f"  Key '{key}' value mismatch: {source_name}='{source[key]}' vs {target_name}='{target[key]}'"
            )
    return errors


def generate_python(mappings: dict[str, str]) -> str:
    lines = [
        '"""Bidirectional mapping between frontend PascalCase and backend lowercase action names."""',
        "",
        "# Frontend (PascalCase) → Backend (lowercase)",
        "FRONTEND_TO_BACKEND: dict[str, str] = {",
    ]
    for key, value in mappings.items():
        lines.append(f'    "{key}": "{value}",')
    lines.append("}")
    lines.append("")
    lines.append("# Backend (lowercase) → Frontend (PascalCase)")
    lines.append("BACKEND_TO_FRONTEND: dict[str, str] = {v: k for k, v in FRONTEND_TO_BACKEND.items()}")
    lines.append("")
    lines.append("")
    lines.append('def to_backend(frontend_name: str) -> str:')
    lines.append('    """Convert frontend action name to backend. Pass through if already backend."""')
    lines.append("    return FRONTEND_TO_BACKEND.get(frontend_name, frontend_name)")
    lines.append("")
    lines.append("")
    lines.append('def to_frontend(backend_name: str) -> str:')
    lines.append('    """Convert backend action name to frontend. Pass through if already frontend."""')
    lines.append("    return BACKEND_TO_FRONTEND.get(backend_name, backend_name)")
    lines.append("")
    return "\n".join(lines)


def generate_typescript(mappings: dict[str, str]) -> str:
    # Output uses single quotes to match this repo's Prettier config.
    lines = [
        "/**",
        " * Bidirectional mapping between frontend PascalCase and backend lowercase action names.",
        " * AUTO-GENERATED from shared/action-map.json — do not edit manually.",
        " */",
        "",
        "export const FRONTEND_TO_BACKEND: Record<string, string> = {",
    ]
    for key, value in mappings.items():
        lines.append(f"  {key}: '{value}',")
    lines.append("};")
    lines.append("")
    lines.append(
        "export const BACKEND_TO_FRONTEND: Record<string, string> = Object.fromEntries("
    )
    lines.append("  Object.entries(FRONTEND_TO_BACKEND).map(([k, v]) => [v, k]),")
    lines.append(");")
    lines.append("")
    lines.append("export function toFrontend(name: string): string {")
    lines.append("  return BACKEND_TO_FRONTEND[name] ?? name;")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate action-map sync across Python/TypeScript/JSON")
    parser.add_argument("--fix", action="store_true", help="Regenerate Python and TypeScript files from JSON source")
    args = parser.parse_args()

    mappings = load_json()
    print(f"JSON source: {len(mappings)} entries")

    if args.fix:
        PY_PATH.write_text(generate_python(mappings), encoding="utf-8")
        print(f"  ✓ Regenerated {PY_PATH.relative_to(ROOT)}")
        TS_PATH.write_text(generate_typescript(mappings), encoding="utf-8")
        print(f"  ✓ Regenerated {TS_PATH.relative_to(ROOT)}")
        print("Fix complete.")
        return

    py_map = parse_python()
    ts_map = parse_typescript()
    print(f"Python:      {len(py_map)} entries")
    print(f"TypeScript:  {len(ts_map)} entries")

    errors: list[str] = []
    errors.extend(compare(mappings, py_map, "JSON", "Python"))
    errors.extend(compare(py_map, mappings, "Python", "JSON"))
    errors.extend(compare(mappings, ts_map, "JSON", "TypeScript"))
    errors.extend(compare(ts_map, mappings, "TypeScript", "JSON"))

    if errors:
        print(f"\n✗ {len(errors)} mismatch(es) found:")
        for e in errors:
            print(e)
        print("\nRun with --fix to regenerate from JSON source.")
        sys.exit(1)
    else:
        print("\n✓ All in sync.")


if __name__ == "__main__":
    main()
