#!/usr/bin/env python3
"""Create and audit bounded Git worktree lanes for Codex tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

MAX_LANES = 3
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class LaneError(RuntimeError):
    """Safe operator-facing lane failure."""


@dataclass(frozen=True)
class Worktree:
    """One parsed Git worktree."""

    path: Path
    head: str
    branch: str | None
    bare: bool
    detached: bool


def run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a bounded local command.

    Parameters
    ----------
    command:
        Argument vector. A shell is never used.
    cwd:
        Optional working directory.
    check:
        Raise ``LaneError`` on non-zero exit when true.

    Returns
    -------
    subprocess.CompletedProcess[str]
        Completed process with captured text output.
    """
    process = subprocess.run(
        list(command),
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and process.returncode != 0:
        detail = (process.stderr or process.stdout or "command failed").strip()
        raise LaneError(f"{' '.join(command)} failed: {detail[:2000]}")
    return process


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run Git without a shell."""
    executable = shutil.which("git")
    if executable is None:
        raise LaneError("Git is not installed or is not on PATH.")
    return run((executable, "-C", str(repo), *args), check=check)


def repository_root(repo: Path) -> Path:
    """Resolve and validate the target repository root."""
    candidate = repo.expanduser().resolve()
    output = git(candidate, "rev-parse", "--show-toplevel").stdout.strip()
    root = Path(output).resolve()
    if not root.is_dir():
        raise LaneError(f"Repository root does not exist: {root}")
    return root


def validate_slug(slug: str) -> str:
    """Validate one lane slug."""
    if not SLUG_RE.fullmatch(slug) or ".." in slug:
        raise LaneError(
            "Lane names must use 1-64 lowercase letters, digits, dots, dashes, "
            "or underscores; they cannot contain '..'."
        )
    return slug


def managed_root(repo_root: Path, home: Path) -> Path:
    """Return the deterministic managed worktree root for a repository."""
    digest = hashlib.sha256(str(repo_root).encode("utf-8")).hexdigest()[:10]
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", repo_root.name).strip("-") or "repo"
    return home.expanduser().resolve() / ".codex" / "worktrees" / f"{name}-{digest}"


def parse_worktrees(raw: str) -> list[Worktree]:
    """Parse ``git worktree list --porcelain`` output."""
    records: list[Worktree] = []
    current: dict[str, str | bool] = {}

    def flush() -> None:
        if "worktree" not in current:
            current.clear()
            return
        records.append(
            Worktree(
                path=Path(str(current["worktree"])).resolve(),
                head=str(current.get("HEAD", "")),
                branch=(
                    str(current["branch"]).removeprefix("refs/heads/")
                    if "branch" in current
                    else None
                ),
                bare=bool(current.get("bare", False)),
                detached=bool(current.get("detached", False)),
            )
        )
        current.clear()

    for line in raw.splitlines():
        if not line:
            flush()
            continue
        key, _, value = line.partition(" ")
        if key in {"bare", "detached", "locked", "prunable"}:
            current[key] = True
        else:
            current[key] = value
    flush()
    return records


def all_worktrees(repo_root: Path) -> list[Worktree]:
    """Read every worktree registered to the repository."""
    raw = git(repo_root, "worktree", "list", "--porcelain").stdout
    return parse_worktrees(raw)


def managed_worktrees(repo_root: Path, home: Path) -> list[Worktree]:
    """Return worktrees beneath the managed Codex lane root."""
    root = managed_root(repo_root, home)
    return [item for item in all_worktrees(repo_root) if item.path.is_relative_to(root)]


def metadata_path(root: Path, slug: str) -> Path:
    """Return the metadata path for one managed lane."""
    return root / ".metadata" / f"{slug}.json"


def write_metadata(
    root: Path,
    slug: str,
    *,
    repo_root: Path,
    lane_path: Path,
    role: str,
    base: str,
    branch: str | None,
) -> None:
    """Write bounded lane metadata outside the worktree."""
    target = metadata_path(root, slug)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "rory-codex-lane/v1",
        "slug": slug,
        "role": role,
        "repository": str(repo_root),
        "path": str(lane_path),
        "base": base,
        "branch": branch,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


def read_metadata(root: Path, slug: str) -> dict[str, object]:
    """Read one optional lane metadata record."""
    target = metadata_path(root, slug)
    if not target.is_file():
        return {}
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LaneError(f"Lane metadata is malformed: {target}") from exc
    if not isinstance(value, dict):
        raise LaneError(f"Lane metadata is not an object: {target}")
    return value


def branch_exists(repo_root: Path, branch: str) -> bool:
    """Return whether a local branch exists."""
    result = git(
        repo_root,
        "show-ref",
        "--verify",
        "--quiet",
        f"refs/heads/{branch}",
        check=False,
    )
    return result.returncode == 0


def create_lane(
    repo_root: Path,
    home: Path,
    slug: str,
    *,
    role: str,
    base: str,
    branch: str | None,
) -> Path:
    """Create one bounded worktree lane."""
    validate_slug(slug)
    root = managed_root(repo_root, home)
    current = managed_worktrees(repo_root, home)
    if len(current) >= MAX_LANES:
        raise LaneError(
            f"Lane limit reached: {len(current)}/{MAX_LANES}. "
            "Remove or finish a lane before creating another."
        )

    lane_path = root / slug
    if lane_path.exists():
        raise LaneError(f"Lane path already exists: {lane_path}")
    root.mkdir(parents=True, exist_ok=True)

    selected_branch: str | None = None
    if role == "author":
        selected_branch = branch or f"codex/{slug}"
        if branch_exists(repo_root, selected_branch):
            git(repo_root, "worktree", "add", str(lane_path), selected_branch)
        else:
            git(
                repo_root,
                "worktree",
                "add",
                "-b",
                selected_branch,
                str(lane_path),
                base,
            )
    else:
        if branch is not None:
            raise LaneError("--branch is valid only for the author role.")
        git(repo_root, "worktree", "add", "--detach", str(lane_path), base)

    write_metadata(
        root,
        slug,
        repo_root=repo_root,
        lane_path=lane_path,
        role=role,
        base=base,
        branch=selected_branch,
    )
    return lane_path


def lane_slug(root: Path, worktree: Worktree) -> str:
    """Return a worktree's relative lane slug."""
    try:
        relative = worktree.path.relative_to(root)
    except ValueError as exc:
        raise LaneError(f"Worktree is outside the managed root: {worktree.path}") from exc
    if len(relative.parts) != 1:
        raise LaneError(f"Unexpected nested lane path: {worktree.path}")
    return relative.name


def list_lanes(repo_root: Path, home: Path) -> list[tuple[str, Worktree, dict[str, object]]]:
    """Return managed lanes with metadata."""
    root = managed_root(repo_root, home)
    rows: list[tuple[str, Worktree, dict[str, object]]] = []
    for worktree in managed_worktrees(repo_root, home):
        slug = lane_slug(root, worktree)
        rows.append((slug, worktree, read_metadata(root, slug)))
    return sorted(rows, key=lambda row: row[0])


def is_dirty(path: Path) -> bool:
    """Return whether a worktree has uncommitted changes."""
    return bool(git(path, "status", "--porcelain=v1").stdout.strip())


def remove_lane(repo_root: Path, home: Path, slug: str) -> Path:
    """Remove one clean managed worktree while retaining its branch."""
    validate_slug(slug)
    root = managed_root(repo_root, home)
    lane_path = (root / slug).resolve()
    if not lane_path.is_relative_to(root):
        raise LaneError("Resolved lane path escaped the managed root.")

    matches = [item for item in managed_worktrees(repo_root, home) if item.path == lane_path]
    if len(matches) != 1:
        raise LaneError(f"No unique managed lane named {slug!r} exists.")
    if is_dirty(lane_path):
        raise LaneError(
            f"Lane {slug!r} has uncommitted changes. Commit, move, or discard them "
            "manually before removal."
        )

    git(repo_root, "worktree", "remove", str(lane_path))
    metadata = metadata_path(root, slug)
    if metadata.exists():
        metadata.unlink()
    return lane_path


def print_rows(repo_root: Path, home: Path) -> int:
    """Print current managed lanes."""
    rows = list_lanes(repo_root, home)
    if not rows:
        print("No managed Codex lanes.")
        return 0
    for slug, worktree, metadata in rows:
        role = str(metadata.get("role", "unknown"))
        branch = worktree.branch or "(detached)"
        dirty = "dirty" if is_dirty(worktree.path) else "clean"
        print(f"{slug}\t{role}\t{branch}\t{dirty}\t{worktree.path}")
    return len(rows)


def audit(repo_root: Path, home: Path) -> int:
    """Audit the three-lane limit and report state."""
    count = print_rows(repo_root, home)
    if count > MAX_LANES:
        raise LaneError(f"Lane limit violated: {count}/{MAX_LANES}.")
    print(f"[ok] managed lanes: {count}/{MAX_LANES}")
    return count


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Create and audit at most three managed Codex worktree lanes."
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--home", type=Path, default=Path.home())

    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create one managed worktree.")
    create.add_argument("slug")
    create.add_argument("--role", choices=("author", "review", "verify"), default="author")
    create.add_argument("--base", default="HEAD")
    create.add_argument("--branch")

    subparsers.add_parser("list", help="List managed worktrees.")
    subparsers.add_parser("audit", help="Check the three-lane limit.")

    remove = subparsers.add_parser(
        "remove",
        help="Remove one clean worktree; its branch is intentionally retained.",
    )
    remove.add_argument("slug")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the lane command."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = repository_root(args.repo)
    home = args.home.expanduser().resolve()

    if args.command == "create":
        path = create_lane(
            repo_root,
            home,
            args.slug,
            role=args.role,
            base=args.base,
            branch=args.branch,
        )
        print(f"[created] {args.role} lane: {path}")
        print(f"[ok] managed lanes: {len(managed_worktrees(repo_root, home))}/{MAX_LANES}")
    elif args.command == "list":
        print_rows(repo_root, home)
    elif args.command == "audit":
        audit(repo_root, home)
    elif args.command == "remove":
        path = remove_lane(repo_root, home, args.slug)
        print(f"[removed] {path}")
        print("The associated branch, if any, was retained.")
    else:
        raise LaneError(f"Unsupported command: {args.command}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LaneError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except KeyboardInterrupt:
        raise SystemExit(130)
