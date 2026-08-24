#!/usr/bin/env python3
"""Validate Rory's Codex engineering system and its local lifecycle."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Sequence


class ValidationError(RuntimeError):
    """Validation failure."""


def run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one command and require success."""
    process = subprocess.run(
        list(command),
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise ValidationError(
            f"{' '.join(command)} failed\nstdout:\n{process.stdout}\nstderr:\n{process.stderr}"
        )
    return process


def initialize_repository(path: Path) -> None:
    """Create one minimal local Git repository."""
    path.mkdir(parents=True)
    run(("git", "init", "-b", "main"), cwd=path)
    run(("git", "config", "user.email", "codex-system@example.invalid"), cwd=path)
    run(("git", "config", "user.name", "Codex System Test"), cwd=path)
    (path / "README.md").write_text("# fixture\n", encoding="utf-8")
    run(("git", "add", "README.md"), cwd=path)
    run(("git", "commit", "-m", "Initialize fixture"), cwd=path)


def validate_installer(root: Path, temporary: Path) -> None:
    """Exercise install, idempotent update, and safe uninstall."""
    installer = root / "tools" / "install_codex_engineering_system.py"
    home = temporary / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    original = (
        'model = "gpt-5.6"\n\n'
        "[agents]\n"
        'default_subagent_model = "gpt-5.6-terra"\n'
    )
    (codex / "config.toml").write_text(original, encoding="utf-8")

    run((sys.executable, str(installer), "--self-check"))
    run((sys.executable, str(installer), "--home", str(home), "--copy"))
    run((sys.executable, str(installer), "--home", str(home), "--copy"))

    installed_skills = sorted((home / ".agents" / "skills").glob("*/SKILL.md"))
    installed_agents = sorted((home / ".codex" / "agents").glob("*.toml"))
    if len(installed_skills) != 4 or len(installed_agents) != 3:
        raise ValidationError("Installer did not create the expected skills and agents.")

    with (codex / "config.toml").open("rb") as handle:
        config = tomllib.load(handle)
    agents = config.get("agents")
    if (
        not isinstance(agents, dict)
        or agents.get("max_concurrent_threads_per_session") != 3
    ):
        raise ValidationError("Installer did not enforce the three-thread limit.")

    run((sys.executable, str(installer), "--home", str(home), "--uninstall"))
    if (codex / "AGENTS.md").exists():
        raise ValidationError("Uninstall left the managed global AGENTS.md.")
    if (codex / "config.toml").read_text(encoding="utf-8") != original:
        raise ValidationError("Uninstall did not restore the pre-existing Codex config.")
    if any((home / ".agents" / "skills").glob("*/SKILL.md")):
        raise ValidationError("Uninstall left managed skills.")
    if any((home / ".codex" / "agents").glob("*.toml")):
        raise ValidationError("Uninstall left managed custom agents.")


def validate_lanes(root: Path, temporary: Path) -> None:
    """Exercise bounded author and read-only worktree lanes."""
    lane_tool = root / "tools" / "codex_lanes.py"
    repository = temporary / "repository"
    home = temporary / "lane-home"
    home.mkdir()
    initialize_repository(repository)

    prefix = (
        sys.executable,
        str(lane_tool),
        "--repo",
        str(repository),
        "--home",
        str(home),
    )
    run((*prefix, "create", "issue-123", "--role", "author"))
    run(
        (
            *prefix,
            "create",
            "review-123",
            "--role",
            "review",
            "--base",
            "codex/issue-123",
        )
    )
    audit = run((*prefix, "audit"))
    if "[ok] managed lanes: 2/3" not in audit.stdout:
        raise ValidationError("Lane audit did not report two managed lanes.")

    run((*prefix, "remove", "review-123"))
    run((*prefix, "remove", "issue-123"))
    final = run((*prefix, "audit"))
    if "[ok] managed lanes: 0/3" not in final.stdout:
        raise ValidationError("Lane cleanup did not return to zero lanes.")


def main() -> int:
    """Run all repository and lifecycle checks."""
    root = Path(__file__).resolve().parent.parent
    required = (
        root / ".agents" / "skills",
        root / ".codex" / "agents",
        root / "codex" / "global-AGENTS.md",
        root / "tools" / "install_codex_engineering_system.py",
        root / "tools" / "codex_lanes.py",
    )
    if not all(path.exists() for path in required):
        raise ValidationError("Required Codex engineering system files are missing.")

    if shutil.which("git") is None:
        raise ValidationError("Git is required for lifecycle validation.")

    with tempfile.TemporaryDirectory(
        prefix="codex-engineering-system-"
    ) as directory:
        temporary = Path(directory)
        validate_installer(root, temporary)
        validate_lanes(root, temporary)

    print("[ok] Codex engineering system validation passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
