#!/usr/bin/env python3
"""
Worktree management commands.

Provides:
    cmd_worktree_create  - Create a git worktree for a task
    cmd_worktree_remove  - Remove a task's worktree
    cmd_worktree_list    - List all active worktrees with git status
    cmd_worktree_status  - Show detailed git status for one worktree
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .git import run_git
from .io import read_json, write_json
from .log import Colors, colored
from .paths import (
    DIR_WORKFLOW,
    FILE_TASK_JSON,
    get_repo_root,
    get_tasks_dir,
)
from .task_utils import resolve_task_dir
from .tasks import iter_active_tasks


# =============================================================================
# Worktree path constants
# =============================================================================

DIR_WORKTREES = "worktrees"


def _worktree_root(repo_root: Path) -> Path:
    """Absolute path to .trellis/worktrees/."""
    return repo_root / DIR_WORKFLOW / DIR_WORKTREES


def _worktree_rel(slug: str) -> str:
    """Repo-relative posix path for a slug's worktree."""
    return f"{DIR_WORKFLOW}/{DIR_WORKTREES}/{slug}"


def _worktree_abs(repo_root: Path, slug: str) -> Path:
    return _worktree_root(repo_root) / slug


def _task_slug(task_data: dict) -> str:
    """Return the task slug (id or name)."""
    return task_data.get("id") or task_data.get("name") or ""


def _branch_exists_local(branch: str, repo_root: Path) -> bool:
    """Return True if a local branch ref exists."""
    rc, _, _ = run_git(
        ["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=repo_root,
    )
    return rc == 0


def _load_task(args_slug: str, repo_root: Path) -> tuple[Path, dict] | None:
    """Resolve task dir + load task.json; print error and return None on failure."""
    task_dir = resolve_task_dir(args_slug, repo_root)
    if not task_dir.is_dir():
        print(colored(f"Error: Task not found: {args_slug}", Colors.RED), file=sys.stderr)
        return None
    task_json = task_dir / FILE_TASK_JSON
    data = read_json(task_json)
    if not data:
        print(colored(f"Error: task.json not found at {task_dir}", Colors.RED), file=sys.stderr)
        return None
    return task_dir, data


# =============================================================================
# Command: worktree create
# =============================================================================

def cmd_worktree_create(args: argparse.Namespace) -> int:
    """Create a git worktree for the given task."""
    repo_root = get_repo_root()
    loaded = _load_task(args.slug, repo_root)
    if loaded is None:
        return 1
    task_dir, data = loaded

    slug = _task_slug(data)
    if not slug:
        print(colored("Error: task.json missing id/name", Colors.RED), file=sys.stderr)
        return 1

    branch = args.branch or data.get("branch") or f"feat/{slug}"
    base_branch = data.get("base_branch") or "main"

    wt_abs = _worktree_abs(repo_root, slug)
    wt_rel = _worktree_rel(slug)

    if wt_abs.exists():
        print(
            colored(f"Error: worktree path already exists: {wt_rel}", Colors.RED),
            file=sys.stderr,
        )
        return 1

    _worktree_root(repo_root).mkdir(parents=True, exist_ok=True)

    # Ensure task dir exists on base_branch — otherwise the new worktree
    # (forked from base_branch) won't see it, and `task.py start <slug>`
    # inside the worktree would fail to resolve the task.
    task_json_rel = (task_dir / FILE_TASK_JSON).relative_to(repo_root).as_posix()
    rc, ls_out, _ = run_git(
        ["ls-tree", base_branch, "--", task_json_rel], cwd=repo_root
    )
    if rc != 0 or not ls_out.strip():
        # task.json not on base_branch → need to bootstrap
        rc, current_out, _ = run_git(["branch", "--show-current"], cwd=repo_root)
        current_branch = current_out.strip() if rc == 0 else ""

        if current_branch != base_branch:
            print(
                colored(
                    f"Error: Task dir '{task_dir.relative_to(repo_root).as_posix()}' "
                    f"is not committed on base branch '{base_branch}', "
                    f"and you are on '{current_branch}'.",
                    Colors.RED,
                ),
                file=sys.stderr,
            )
            print(
                f"Fix: `git checkout {base_branch}` and re-run, "
                f"or change base via `task.py set-base-branch {slug} {current_branch}`.",
                file=sys.stderr,
            )
            return 1

        # On base_branch — safe to auto-commit the task dir so the new
        # worktree (forked from this commit) can see it.
        task_dir_rel = task_dir.relative_to(repo_root).as_posix()
        rc, _, err = run_git(["add", task_dir_rel], cwd=repo_root)
        if rc != 0:
            print(
                colored(f"Error: git add failed: {err.strip()}", Colors.RED),
                file=sys.stderr,
            )
            return 1
        rc, _, err = run_git(
            ["commit", "-m", f"chore(task): bootstrap {slug} 任务目录"],
            cwd=repo_root,
        )
        if rc != 0:
            print(
                colored(f"Error: auto-commit failed: {err.strip()}", Colors.RED),
                file=sys.stderr,
            )
            return 1
        print(
            colored(
                f"✓ Auto-committed {task_dir_rel} on {base_branch}", Colors.GREEN
            )
        )

    if _branch_exists_local(branch, repo_root):
        rc, _, err = run_git(
            ["worktree", "add", str(wt_abs), branch],
            cwd=repo_root,
        )
    else:
        rc, _, err = run_git(
            ["worktree", "add", str(wt_abs), "-b", branch, base_branch],
            cwd=repo_root,
        )

    if rc != 0:
        print(
            colored(f"Error: git worktree add failed:\n{err.strip()}", Colors.RED),
            file=sys.stderr,
        )
        return 1

    data["worktree_path"] = wt_rel
    if not data.get("branch"):
        data["branch"] = branch
    write_json(task_dir / FILE_TASK_JSON, data)

    print(colored(f"✓ Worktree created: {wt_rel}", Colors.GREEN))
    print(f"  Branch: {branch}")
    print(f"  Base:   {base_branch}")
    print(f"  Task:   {task_dir.relative_to(repo_root).as_posix()}")
    print(str(wt_abs))
    return 0


# =============================================================================
# Command: worktree remove
# =============================================================================

def cmd_worktree_remove(args: argparse.Namespace) -> int:
    """Remove a task's worktree (refuses if dirty / ahead unless --force)."""
    repo_root = get_repo_root()
    loaded = _load_task(args.slug, repo_root)
    if loaded is None:
        return 1
    task_dir, data = loaded

    wt_rel = data.get("worktree_path")
    if not wt_rel:
        print(
            colored("Error: task has no worktree (worktree_path is null)", Colors.RED),
            file=sys.stderr,
        )
        return 1

    wt_abs = repo_root / wt_rel
    branch = data.get("branch")
    base_branch = data.get("base_branch") or "main"
    force = bool(getattr(args, "force", False))

    if not force and wt_abs.is_dir():
        rc, out, _ = run_git(["status", "--porcelain"], cwd=wt_abs)
        if rc == 0 and out.strip():
            print(
                colored("Error: worktree has uncommitted changes:", Colors.RED),
                file=sys.stderr,
            )
            print(out, file=sys.stderr)
            print("Use --force to override.", file=sys.stderr)
            return 1

        if branch:
            rc, out, _ = run_git(
                ["log", "--oneline", f"{base_branch}..{branch}"],
                cwd=repo_root,
            )
            if rc == 0 and out.strip():
                ahead = len(out.strip().splitlines())
                print(
                    colored(
                        f"Error: branch {branch} has {ahead} commit(s) ahead of {base_branch}:",
                        Colors.RED,
                    ),
                    file=sys.stderr,
                )
                print(out, file=sys.stderr)
                print(
                    "Use --force to override (commits remain on the branch — only the worktree is removed).",
                    file=sys.stderr,
                )
                return 1

    git_args = ["worktree", "remove"]
    if force:
        git_args.append("--force")
    git_args.append(str(wt_abs))

    rc, _, err = run_git(git_args, cwd=repo_root)
    if rc != 0:
        print(
            colored(f"Error: git worktree remove failed:\n{err.strip()}", Colors.RED),
            file=sys.stderr,
        )
        return 1

    data["worktree_path"] = None
    write_json(task_dir / FILE_TASK_JSON, data)

    print(colored(f"✓ Worktree removed: {wt_rel}", Colors.GREEN))
    if branch:
        print(f"  Branch {branch} retained.")
    return 0


# =============================================================================
# Command: worktree list
# =============================================================================

def cmd_worktree_list(args: argparse.Namespace) -> int:
    """List all active worktrees registered in task.json files."""
    _ = args
    repo_root = get_repo_root()
    tasks_dir = get_tasks_dir(repo_root)

    rows: list[tuple[str, str, str, str, str]] = []
    for task in iter_active_tasks(tasks_dir):
        wt_rel = task.raw.get("worktree_path")
        if not wt_rel:
            continue

        wt_abs = repo_root / wt_rel
        branch = task.raw.get("branch") or "?"
        base_branch = task.raw.get("base_branch") or "main"

        ahead = behind = "?"
        if branch != "?":
            rc, out, _ = run_git(
                ["rev-list", "--left-right", "--count", f"{base_branch}...{branch}"],
                cwd=repo_root,
            )
            if rc == 0 and out.strip():
                parts = out.strip().split()
                if len(parts) == 2:
                    behind, ahead = parts

        if wt_abs.is_dir():
            rc, out, _ = run_git(["status", "--porcelain"], cwd=wt_abs)
            dirty = "yes" if (rc == 0 and out.strip()) else "no"
        else:
            dirty = "MISSING"

        rows.append(
            (task.dir_name, branch, wt_rel, f"+{ahead}/-{behind}", dirty)
        )

    if not rows:
        print("No active worktrees.")
        return 0

    headers = ("TASK", "BRANCH", "PATH", "AHEAD/BEHIND", "DIRTY")
    widths = [
        max(len(headers[i]), max(len(r[i]) for r in rows))
        for i in range(len(headers))
    ]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*("-" * w for w in widths)))
    for row in rows:
        print(fmt.format(*row))
    return 0


# =============================================================================
# Command: worktree status
# =============================================================================

def cmd_worktree_status(args: argparse.Namespace) -> int:
    """Show detailed git status for a single worktree."""
    repo_root = get_repo_root()
    loaded = _load_task(args.slug, repo_root)
    if loaded is None:
        return 1
    _, data = loaded

    wt_rel = data.get("worktree_path")
    if not wt_rel:
        print(
            colored("Error: task has no worktree (worktree_path is null)", Colors.RED),
            file=sys.stderr,
        )
        return 1

    wt_abs = repo_root / wt_rel
    branch = data.get("branch") or "?"
    base_branch = data.get("base_branch") or "main"

    print(colored(f"Worktree: {wt_rel}", Colors.BLUE))
    print(f"  Branch: {branch}")
    print(f"  Base:   {base_branch}")
    print()

    if not wt_abs.is_dir():
        print(colored("MISSING — worktree path does not exist on disk.", Colors.RED))
        return 1

    if branch != "?":
        rc, out, _ = run_git(
            ["rev-list", "--left-right", "--count", f"{base_branch}...{branch}"],
            cwd=repo_root,
        )
        if rc == 0 and out.strip():
            parts = out.strip().split()
            if len(parts) == 2:
                behind, ahead = parts
                print(f"  Ahead of {base_branch}: {ahead}")
                print(f"  Behind {base_branch}:   {behind}")
                print()

    print(colored("git status:", Colors.BLUE))
    rc, out, _ = run_git(["status"], cwd=wt_abs)
    if rc == 0:
        print(out.rstrip())
    print()

    if branch != "?":
        print(colored(f"Commits on {branch} ahead of {base_branch}:", Colors.BLUE))
        rc, out, _ = run_git(
            ["log", "--oneline", f"{base_branch}..{branch}"],
            cwd=repo_root,
        )
        if rc == 0:
            if out.strip():
                print(out.rstrip())
            else:
                print("  (none)")

    return 0
